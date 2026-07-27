"""
Enhanced web API server for JARVIS web UI.

Provides comprehensive provider catalog, model selection, and dynamic model loading
supporting all providers listed in the provider list.
"""

from __future__ import annotations
import asyncio
import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, HTTPException, Body, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles


from app.config.settings import get_settings, Settings
from app.config.prompt import SYSTEM_PROMPT
from app.config.version import VERSION
from app.memory.manager import MemoryManager
from app.memory.fact_extractor import extract_facts
from app.conversation.manager import ConversationManager
from app.prompt.builder import PromptBuilder
from app.context.manager import ContextWindowManager
from app.memory.retrieval import KeywordRetriever
from app.memory.hybrid_retriever import HybridRetriever
from app.memory.vector_retriever import VectorRetriever
from app.memory.conversation_store import ConversationVectorStore
from app.models.switcher import ModelSwitcher
from app.models.router import TaskType
from app.models.factory import create_client
from app.models.exceptions import ModelError
from app.utils.logging_setup import setup_logging, get_logger
from app.utils.provider_catalog import get_all_providers, get_provider_models, get_all_models_summary, search_all_providers

# Imports for remote OCR health checking
from app.utils.server_manager import ollama_model_names, llamacpp_live_models
from app.utils.model_selector import _categorize_cloud_models
from app.utils.openrouter_catalog import fetch_openrouter_models

# Path setup
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
logger = get_logger(__name__)
def check_remote_health(url: str | None, timeout: int = 5) -> dict:
    """Check a remote OCR service for basic health."""
    if not url:
        return {"ok": False, "error": "remote_ocr_url not configured"}
    try:
        import requests
        from urllib.parse import urlparse, urlunparse

        p = urlparse(url)
        base = urlunparse((p.scheme, p.netloc, "", "", "", ""))
        health_url = base.rstrip("/") + "/health"
        try:
            r = requests.get(health_url, timeout=timeout)
            if r.status_code == 200:
                try:
                    content = r.json()
                except Exception:
                    content = r.text
                return {"ok": True, "status_code": r.status_code, "detail": content}
        except Exception:
            pass
        r2 = requests.get(url, timeout=timeout)
        if r2.status_code == 200:
            return {"ok": True, "status_code": r2.status_code}
        return {"ok": False, "status_code": r2.status_code}
    except Exception:
        try:
            from urllib import request as _request
            from urllib.parse import urlparse, urlunparse

            p = urlparse(url)
            base = urlunparse((p.scheme, p.netloc, "", "", "", ""))
            health_url = base.rstrip("/") + "/health"
            req = _request.Request(health_url, method="GET")
            with _request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return {"ok": True, "status_code": resp.status, "detail": raw}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
class JarvisWebEngine:
    """Enhanced web JARVIS engine with provider catalog support."""

    def __init__(self) -> None:
        self.settings: Settings = get_settings()
        self.memory = MemoryManager(
            retriever=HybridRetriever(
                vector=VectorRetriever(
                    persist_dir=str(self.settings.paths.chroma_dir),
                    ollama_url=self.settings.paths.ollama_url,
                    embed_model=self.settings.paths.embed_model,
                ),
                keyword=KeywordRetriever(min_keyword_overlap=1),
            )
        )
        self.prompt_builder = PromptBuilder(system_prompt=SYSTEM_PROMPT)
        self.context_manager = ContextWindowManager(
            max_tokens=self.settings.context.max_tokens,
            safety_margin=self.settings.context.safety_margin,
            model_name=self.settings.default_model,
        )
        self.switcher = ModelSwitcher(self.settings)
        self.conv_store = ConversationVectorStore(
            persist_dir=str(self.settings.paths.chroma_dir),
            ollama_url=self.settings.paths.ollama_url,
            embed_model=self.settings.paths.embed_model,
        )
        if self.conv_store.count() == 0:
            try:
                from app.conversation.manager import ConversationManager as _CM
                default_cm = _CM()
                indexed = self.conv_store.index_history(default_cm.get_all())
                if indexed > 0:
                    logger.info("Indexed %d exchanges into conversation store", indexed)
            except Exception:
                pass
        self.conversations: dict[str, ConversationManager] = {}
        self.stop_requested: bool = False
        self._stop_lock = threading.Lock()

    def get_or_create_conversation(self, conv_id: str) -> ConversationManager:
        cm = self.conversations.get(conv_id)
        if cm is None:
            path = self.settings.paths.conversations_dir / f"{conv_id}.json"
            cm = ConversationManager(path=str(path))
            self.conversations[conv_id] = cm
        return cm

    def list_conversations(self) -> list[dict]:
        convs = []
        d = self.settings.paths.conversations_dir
        d.mkdir(parents=True, exist_ok=True)
        for p in sorted(d.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            cid = p.stem
            try:
                cm = self.get_or_create_conversation(cid)
                messages = cm.get_all()
                last = messages[-1].content if messages else ""
                title = (messages[0].content[:40] if messages else "(empty)")
                convs.append({
                    "id": cid,
                    "title": title,
                    "message_count": len(messages),
                    "preview": last[:80],
                    "updated_at": p.stat().st_mtime,
                })
            except Exception:
                continue
        return convs

    def request_stop(self) -> None:
        with self._stop_lock:
            self.stop_requested = True

    def clear_stop(self) -> None:
        with self._stop_lock:
            self.stop_requested = False

    def should_stop(self) -> bool:
        with self._stop_lock:
            return self.stop_requested
def build_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


_MAX_ATTACHMENT_TEXT = 120_000


def _looks_like_text(name: str, mime: str) -> bool:
    """Check if a file appears to be text-like based on name/mime."""
    mime = (mime or "").lower()
    name = (name or "").lower()
    if mime.startswith("text/") or "json" in mime or "xml" in mime:
        return True
    for ext in (".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml",
                ".py", ".js", ".ts", ".go", ".c", ".cpp", ".h", ".rs", ".java",
                ".tex", ".log", ".toml", ".ini", ".cfg", ".sh", ".bat", ".ps1"):
        if name.endswith(ext):
            return True
    return False


def extract_file_text(name: str, mime: str, raw: bytes) -> str:
    """Extract text from uploaded files (PDF, DOCX, or text)."""
    name = name or "file"
    if _looks_like_text(name, mime):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="replace")
    low = name.lower()
    if low.endswith(".pdf"):
        # Try pdftotext for PDF extraction
        try:
            import subprocess
            out = subprocess.run(
                ["pdftotext", "-", "-"], input=raw, capture_output=True, timeout=30
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.decode("utf-8", errors="replace")
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            pass
        return ("[PDF file — text extraction unavailable. Install poppler "
                "(`apt install poppler-utils`) to read PDF text.]")
    if low.endswith(".docx"):
        try:
            import docx
            import io
            d = docx.Document(io.BytesIO(raw))
            return "\n".join(p.text for p in d.paragraphs if p.text)
        except Exception:
            return "[DOCX file — install `python-docx` to read this file's text.]"
    return f"[{name} — binary file ({len(raw)} bytes); text content not readable.]"
class EnhancedWebAPIServer:
    """Enhanced JARVIS web API server with provider catalog integration."""

    def __init__(self) -> None:
        self.app = FastAPI(title="JARVIS Web UI (Enhanced)", version=VERSION)
        self.app.state.engine = JarvisWebEngine()
        self._setup_routes()

    def _setup_routes(self) -> None:
        engine = self.app.state.engine

        @self.app.get("/api/providers")
        def get_providers():
            """Get all available providers with live status."""
            try:
                providers = get_all_providers()
                enriched = []
                for provider in providers:
                    enriched.append({
                        "key": provider["key"],
                        "name": provider["name"],
                        "status": provider["status"],
                        "has_key": provider["has_key"],
                        "model_count": provider.get("model_count", 0),
                        "categories": provider.get("categories", []),
                        "is_openai_compatible": provider.get("is_openai_compatible", False),
                        "free_models_available": provider.get("free_models_available", False),
                    })
                return {"providers": enriched}
            except Exception as e:
                logger.warning(f"Failed to get providers: {e}")
                return {"providers": []}

        @self.app.get("/api/models")
        def get_models():
            """Get available models - format expected by frontend."""
            try:
                # Build model groups similar to api/server.py
                settings = engine.settings
                from app.utils.server_manager import ollama_model_names, llamacpp_live_models
                from app.utils.model_selector import _categorize_cloud_models
                
                cloud = _categorize_cloud_models(settings)
                ollama_models = ollama_model_names(settings.paths.ollama_url)

                groups: list[dict] = []

                # Ollama (local, free)
                groups.append({
                    "provider": "ollama",
                    "label": "Ollama (local, free)",
                    "requires_key": False,
                    "models": [{"id": f"ollama:{m}", "name": m, "backend": "ollama"} for m in ollama_models],
                })

                if "omni" in engine.switcher._routers:
                    groups.append({
                        "provider": "omni",
                        "label": "Omni (all providers)",
                        "requires_key": False,
                        "models": [{"id": "omni", "name": "Omni", "backend": "omni"}],
                    })

                # llama.cpp local servers that are actually running
                live = llamacpp_live_models(settings)
                if live:
                    groups.append({
                        "provider": "llamacpp",
                        "label": "llama.cpp (local server)",
                        "requires_key": False,
                        "models": [{"id": f"model:{m['key']}", "name": m["name"], "backend": "llamacpp"} for m in live],
                    })

                # Cloud providers — show configured provider models by provider
                cloud_providers = [
                    ("google", "Google", "GOOGLE_API_KEY"),
                    ("grok", "Grok", "XAI_API_KEY"),
                    ("openrouter", "OpenRouter", "OPENROUTER_API_KEY"),
                ]
                for provider, label, env_var in cloud_providers:
                    if provider == "openrouter":
                        continue
                    keys = cloud.get(provider, [])
                    if not keys:
                        continue
                    seen: set[tuple[str, str]] = set()
                    provider_models: list[dict] = []
                    for k in keys:
                        cfg = settings.models[k]
                        key = (cfg.backend or "", cfg.name or "")
                        if key in seen:
                            continue
                        seen.add(key)
                        provider_models.append({
                            "id": f"model:{k}",
                            "name": cfg.name,
                            "backend": cfg.backend,
                        })
                    if provider_models:
                        groups.append({
                            "provider": provider,
                            "label": label,
                            "requires_key": True,
                            "key_env": env_var,
                            "key_set": bool(os.environ.get(env_var, "")),
                            "models": provider_models,
                        })

                # OpenRouter live catalog
                if bool(os.environ.get("OPENROUTER_API_KEY", "")):
                    # Pick a default free model if available
                    default_free_model = next(
                        (settings.models[k].name for k in cloud.get("openrouter", [])
                         if "free" in settings.models[k].name.lower()),
                        "anthropic/claude-3.5-sonnet",
                    )
                    try:
                        from app.utils.openrouter_catalog import search_openrouter_models
                        free_candidates = search_openrouter_models("", limit=1, free_only=True)
                        if free_candidates:
                            default_free_model = free_candidates[0]["id"]
                    except Exception:
                        pass

                    groups.append({
                        "provider": "openrouter",
                        "label": "OpenRouter — live catalog",
                        "requires_key": True,
                        "key_env": "OPENROUTER_API_KEY",
                        "key_set": True,
                        "dynamic": True,
                        "models": [],
                    })

                return {
                    "active_profile": engine.switcher.active_profile,
                    "groups": groups,
                    "version": VERSION,
                }
            except Exception as e:
                logger.warning(f"Failed to get models: {e}")
                return {"active_profile": None, "groups": [], "version": VERSION}

        @self.app.get("/api/models/catalog")
        def get_model_catalog(provider: str = "openrouter", query: str = "", limit: int = 50, free_only: bool = False):
            """Get live models from any provider."""
            if provider != "openrouter":
                raise HTTPException(400, "Only 'openrouter' catalog is supported")
            try:
                from app.utils.openrouter_catalog import search_openrouter_models
                models = search_openrouter_models(query, limit=limit, free_only=free_only)
                return {"provider": provider, "count": len(models), "models": models, "free_only": free_only}
            except Exception as e:
                logger.warning(f"Failed to get model catalog for {provider}: {e}")
                return {"provider": provider, "count": 0, "models": [], "free_only": free_only}

        @self.app.get("/api/models/search")
        def search_models(query: str = "", limit: int = 50):
            """Search models across all providers."""
            try:
                return search_all_providers(query, limit)
            except Exception as e:
                logger.warning(f"Failed to search models: {e}")
                return []

        @self.app.post("/api/models/select")
        def select_model(payload: dict = Body(...)):
            """Select a model with full provider support."""
            try:
                model_id = payload.get("model_id")
                backend = payload.get("backend")
                model = payload.get("model")
                
                if not model_id:
                    raise HTTPException(400, "model_id required")
                
                # Dynamic selection: {"model_id": "dyn", "backend": "...", "model": "..."}
                if model_id == "dyn" or payload.get("dynamic"):
                    if not backend or not model:
                        raise HTTPException(400, "backend and model required for dynamic selection")
                    result = apply_dynamic_selection(engine, backend, model)
                    if not result.get("ok"):
                        raise HTTPException(400, result.get("error", "selection failed"))
                    return result
                
                if model_id.startswith("dyn:"):
                    return apply_dynamic_selection(engine, "openrouter", model_id[4:])
                
                result = apply_model_selection(engine, model_id)
                if not result.get("ok"):
                    raise HTTPException(400, result.get("error", "selection failed"))
                return result
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Model selection failed: {e}")
                raise HTTPException(400, str(e))

        @self.app.post("/api/settings")
        def save_settings(payload: dict = Body(...)):
            """Save API keys and settings."""
            try:
                # Update environment variables
                key_map = {
                    "google_api_key": "GOOGLE_API_KEY",
                    "xai_api_key": "XAI_API_KEY",
                    "openrouter_api_key": "OPENROUTER_API_KEY",
                    "openai_api_key": "OPENAI_API_KEY",
                    "cohere_api_key": "COHERE_API_KEY",
                    "mistral_api_key": "MISTRAL_API_KEY",
                    "groq_api_key": "GROQ_API_KEY",
                    "github_token": "GITHUB_TOKEN",
                    "huggingface_token": "HF_API_TOKEN",
                    "zhipu_api_key": "ZHIPU_API_KEY",
                    "cloudflare_api_token": "CLOUDFLARE_API_TOKEN",
                    "cloudflare_account_id": "CLOUDFLARE_ACCOUNT_ID",
                }
                
                changed = []
                for payload_key, env_var in key_map.items():
                    if payload_key in payload and payload[payload_key]:
                        os.environ[env_var] = payload[payload_key]
                        changed.append(env_var)
                
                # Rebuild switcher with new settings
                engine.switcher = ModelSwitcher(engine.settings)
                
                return {"ok": True, "changed": changed}
            except Exception as e:
                logger.warning(f"Settings save failed: {e}")
                raise HTTPException(400, str(e))

        @self.app.get("/api/settings")
        def get_settings_endpoint():
            """Get current settings."""
            try:
                engine = self.app.state.engine
                settings = engine.settings
                
                # Check which API keys are present
                key_status = {
                    "google": bool(os.environ.get("GOOGLE_API_KEY", "")),
                    "xai": bool(os.environ.get("XAI_API_KEY", "")),
                    "openrouter": bool(os.environ.get("OPENROUTER_API_KEY", "")),
                    "openai": bool(os.environ.get("OPENAI_API_KEY", "")),
                }
                
                return {
                    "use_developer_keys": True,
                    "providers": key_status,
                    "context_max_tokens": settings.context.max_tokens,
                    "memory_retrieval_limit": settings.memory.retrieval_limit,
                }
            except Exception as e:
                logger.warning(f"Failed to get settings: {e}")
                return {"use_developer_keys": True, "providers": {}, "context_max_tokens": 4096, "memory_retrieval_limit": 20}

        @self.app.get("/api/conversations")
        def get_conversations():
            """Get all conversations."""
            try:
                return {"conversations": engine.list_conversations()}
            except Exception as e:
                logger.warning(f"Failed to get conversations: {e}")
                return {"conversations": []}

        @self.app.post("/api/conversations")
        def create_conversation(payload: dict = Body(default={})):
            """Create a new conversation."""
            try:
                cid = payload.get("id") or uuid.uuid4().hex
                engine.get_or_create_conversation(cid)
                return {"id": cid}
            except Exception as e:
                logger.warning(f"Failed to create conversation: {e}")
                raise HTTPException(400, str(e))

        @self.app.get("/api/conversations/{conv_id}")
        def get_conversation(conv_id: str):
            """Get a conversation."""
            try:
                cm = engine.get_or_create_conversation(conv_id)
                return {
                    "id": conv_id,
                    "messages": [m.to_dict() for m in cm.get_all()],
                }
            except Exception as e:
                logger.warning(f"Failed to get conversation {conv_id}: {e}")
                raise HTTPException(404, str(e))

        @self.app.delete("/api/conversations/{conv_id}")
        def delete_conversation(conv_id: str):
            """Delete a conversation."""
            try:
                engine.conversations.pop(conv_id, None)
                p = engine.settings.paths.conversations_dir / f"{conv_id}.json"
                if p.exists():
                    p.unlink()
                return {"ok": True}
            except Exception as e:
                logger.warning(f"Failed to delete conversation {conv_id}: {e}")
                raise HTTPException(400, str(e))

        @self.app.post("/api/chat")
        async def chat(request: Request):
            """Chat endpoint with SSE streaming support."""
            ctype = request.headers.get("content-type", "")
            conv_id = None
            message = ""
            atts = []

            if "multipart/form-data" in ctype:
                form = await request.form()
                conv_id = form.get("conversation_id") or ""
                message = form.get("message", "")
                for up in form.getlist("attachments"):
                    try:
                        raw = await up.read()
                    except Exception:
                        continue
                    if len(raw) > 5 * 1024 * 1024:
                        continue
                    fname = os.path.basename(up.filename or "upload.txt")
                    content = extract_file_text(fname, up.content_type or "", raw)
                    if len(content) > _MAX_ATTACHMENT_TEXT:
                        content = content[:_MAX_ATTACHMENT_TEXT] + "\n…[truncated]"
                    atts.append({"name": fname, "content": content})
            else:
                try:
                    body = await request.json()
                except Exception:
                    body = {}
                if not isinstance(body, dict):
                    body = {}
                conv_id = body.get("conversation_id") or ""
                message = body.get("message", "")

            # Ensure conv_id is set for both multipart and JSON requests
            conv_id = conv_id or uuid.uuid4().hex

            if not message:
                raise HTTPException(400, "message required")

            # Use a thread executor for streaming so we don't block the event loop.
            async def event_gen():
                loop = asyncio.get_event_loop()
                queue: asyncio.Queue = asyncio.Queue()

                def producer():
                    try:
                        for chunk in run_chat_stream(engine, conv_id, message, atts):
                            asyncio.run_coroutine_threadsafe(queue.put(chunk), loop)
                    except Exception as e:
                        asyncio.run_coroutine_threadsafe(
                            queue.put(build_event("error", {"message": str(e)})), loop
                        )
                    finally:
                        asyncio.run_coroutine_threadsafe(queue.put(None), loop)

                fut = loop.run_in_executor(None, producer)
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    yield item
                await fut

            return StreamingResponse(
                event_gen(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        @self.app.post("/api/stop")
        def stop():
            """Stop the current generation."""
            try:
                self.app.state.engine.request_stop()
                return {"ok": True}
            except Exception as e:
                logger.warning(f"Stop failed: {e}")
                raise HTTPException(400, str(e))

        @self.app.get("/api/memories")
        def get_memories():
            """Get stored memories."""
            try:
                memories = engine.memory.get_all()
                return {
                    "memories": [
                        {
                            "category": m.category,
                            "memory_type": m.memory_type,
                            "value": m.value,
                            "access_count": m.access_count,
                        }
                        for m in memories
                    ]
                }
            except Exception as e:
                logger.warning(f"Failed to get memories: {e}")
                return {"memories": []}

        @self.app.get("/api/health")
        def health():
            """Health check."""
            return {
                "status": "ok",
                "version": VERSION,
                "timestamp": str(datetime.now().isoformat()),
            }

        # Serve frontend
        if FRONTEND_DIR.exists():
            self.app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
        else:
            @self.app.get("/")
            def index():
                return {"message": "JARVIS Web UI - Frontend not found at /frontend/", "version": VERSION}
def apply_model_selection(engine: JarvisWebEngine, model_id: str) -> dict:
    """Apply model selection with full provider support."""
    switcher = engine.switcher
    
    if model_id in switcher._routers:
        ok = switcher.switch(model_id)
        if ok:
            return {"ok": True, "active": switcher.active_profile, "name": model_id}
        return {"ok": False, "error": f"Profile '{model_id}' is not usable"}
    
    if model_id.startswith("ollama:"):
        model_name = model_id[len("ollama:"):]
        from app.models.ollama_client import OllamaClient
        from app.models.router import ModelRouter as _Router
        
        try:
            client = OllamaClient(
                model=model_name,
                base_url=engine.settings.paths.ollama_url,
                role="general",
            )
        except Exception as e:
            return {"ok": False, "error": f"Could not create Ollama client: {e}"}
        
        router = _Router()
        for role in ["general", "code", "reasoning", "docs", "stem", "autocomplete"]:
            try:
                router.register(TaskType(role), client)
            except ValueError:
                pass
        router.set_default(client)
        key = f"ollama:{model_name}"
        switcher._routers[key] = router
        switcher._active_profile = key
        return {"ok": True, "active": key, "name": model_name}
    
    if model_id.startswith("model:"):
        key = model_id[len("model:"):]
        ok = switcher.switch_to_model(key)
        if ok:
            return {"ok": True, "active": switcher.active_profile, "name": key}
        return {"ok": False, "error": f"Model '{key}' is not loaded (server down / key missing?)"}
    
    return {"ok": False, "error": f"Unknown model id '{model_id}'"}
def apply_dynamic_selection(engine: JarvisWebEngine, backend: str, model_id: str) -> dict:
    """Apply dynamic model selection for any provider."""
    key_env = {
        "openrouter": "OPENROUTER_API_KEY",
        "google": "GOOGLE_API_KEY",
        "grok": "XAI_API_KEY",
        "xai": "XAI_API_KEY",
        "github": "GITHUB_TOKEN",
        "mistral": "MISTRAL_API_KEY",
        "cohere": "COHERE_API_KEY",
        "groq": "GROQ_API_KEY",
        "huggingface": "HF_API_TOKEN",
        "zhipu": "ZHIPU_API_KEY",
        "cloudflare": "CLOUDFLARE_API_TOKEN",
    }.get(backend)
    
    if not key_env:
        return {"ok": False, "error": f"Unknown backend '{backend}'"}
    
    if not os.environ.get(key_env, ""):
        return {"ok": False, "error": f"{key_env} is not set — add it in Settings"}
    
    ok = engine.switcher.switch_to_dynamic_model(backend, model_id, key_env)
    if ok:
        return {
            "ok": True,
            "active": engine.switcher.active_profile,
            "name": model_id,
            "dynamic": True,
        }
    
    return {"ok": False, "error": f"Could not load {backend} model '{model_id}'"}
def run_chat_stream(engine: JarvisWebEngine, conv_id: str, user_text: str, attachments=None):
    """Generator yielding SSE chunks for a single chat turn.

    Yields ``event: token`` lines for streamed model output, plus ``event:
    done`` / ``event: error`` bookends. Honors engine.should_stop() so the
    frontend's Stop button can abort mid-generation.

    ``attachments`` is an optional list of {name, content} dicts sent inline
    with the chat request (the preferred path).
    """
    import queue as _queue

    engine.clear_stop()
    cm = engine.get_or_create_conversation(conv_id)

    # Inline attachments, if any, are injected as context for this turn only.
    attachments = attachments or []
    if attachments:
        att_block = "\n\n".join(
            f"--- File: {a['name']} ---\n{a['content']}" for a in attachments
        )
        user_text = f"{user_text}\n\n[Attached files]\n{att_block}"

    # Pipeline mirrors app/main.py
    cm.add_message("user", user_text)

    facts = extract_facts(user_text) if not attachments else extract_facts(
        user_text.split("[Attached files]")[0]
    )
    for fact in facts:
        stored = engine.memory.store(fact)
        if stored:
            yield build_event("memory", {
                "memory_type": stored.memory_type,
                "value": stored.value,
            })

    relevant_memories = engine.memory.retrieve(user_text, limit=engine.settings.memory.retrieval_limit)
    past_exchanges = engine.conv_store.search(user_text, limit=2)

    messages = engine.prompt_builder.build(
        memories=relevant_memories,
        conversation=cm.get_recent_formatted(),
        past_exchanges=past_exchanges,
    )

    fitted_messages = engine.context_manager.fit(messages)

    selected_model = engine.switcher.router.default_model
    if selected_model is None:
        yield build_event("error", {"message": "No active model. Pick one in Settings."})
        cm.pop_last_message()
        return

    full_content = ""

    # Tokens pushed from the client's on_token callback into a thread-safe
    # queue; we drain it here so we can interleave stop checks between tokens.
    token_q: "_queue.Queue" = _queue.Queue()

    def on_token(t: str):
        token_q.put(t)

    def _generate():
        try:
            selected_model.generate(fitted_messages, stream=True, on_token=on_token)
        except Exception as e:  # network / model errors
            token_q.put(f"__ERROR__::{e}")
        finally:
            token_q.put(None)  # sentinel: stream finished

    gen_thread = threading.Thread(target=_generate, daemon=True)
    gen_thread.start()

    while True:
        if engine.should_stop():
            yield build_event("stopped", {"message": "Generation stopped."})
            gen_thread.join(timeout=2)
            break
        try:
            item = token_q.get(timeout=0.2)
        except _queue.Empty:
            if not gen_thread.is_alive():
                break
            continue
        if item is None:
            break
        if isinstance(item, str) and item.startswith("__ERROR__::"):
            yield build_event("error", {"message": str(item[len("__ERROR__::"):])})
            cm.pop_last_message()
            return
        full_content += item
        yield build_event("token", {"token": item})

    gen_thread.join(timeout=1)
    if not full_content:
        cm.pop_last_message()
        return

    cm.add_message("assistant", full_content)
    try:
        engine.conv_store.add_exchange(user_text, full_content)
    except Exception:  # pragma: no cover - non-fatal
        pass

    stats = engine.context_manager.get_stats()
    yield build_event("done", {
        "model": selected_model.model_name,
        "truncated": bool(stats and stats.was_trimmed),
    })
def main():
    """Run the enhanced JARVIS web API server."""
    try:
        server = EnhancedWebAPIServer()
        uvicorn.run(
            server.app,
            host="0.0.0.0",
            port=8000,
            reload=False,
        )
    except Exception as e:
        logger.error(f"Failed to start JARVIS web API server: {e}")
        raise
if __name__ == "__main__":
    import uvicorn
    main()


def create_app() -> FastAPI:
    """Factory function for uvicorn --factory mode."""
    server = EnhancedWebAPIServer()
    return server.app






