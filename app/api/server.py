"""
FastAPI server for the JARVIS web UI.

This module wraps the existing JARVIS pipeline (memory, conversation,
model router/switcher, fact extraction, context window) and exposes it over
HTTP so the static frontend in ``frontend/`` can drive it.

Endpoints
---------
* ``GET  /api/models``            — list available models / backends
* ``POST /api/settings``          — update runtime settings (API keys, dev keys)
* ``GET  /api/settings``          — current non-secret settings
* ``GET  /api/conversations``     — list saved conversations
* ``POST /api/conversations``     — create a new conversation
* ``GET  /api/conversations/{id}``— load a conversation's messages
* ``DELETE /api/conversations/{id}`` — delete a conversation
* ``POST /api/chat``              — send a message (SSE streaming response)
* ``POST /api/stop``              — request cancellation of the active stream
* ``POST /api/files``             — upload a text/markdown file to attach
* ``GET  /api/memories``          — view stored memories
* ``GET  /``  and static assets   — serve the web UI

The server keeps one global JARVIS "engine" (the in-memory singletons from
``app/main.py``) plus a per-conversation :class:`ConversationManager`. Chat
history is therefore fully server-side and keyed by a conversation id.

Run it with::

    python -m app.api.server

or import :func:`create_app` and mount it however you like.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import threading
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env exactly like app/main.py does, before any settings are built.
# override=True so a key defined in .env wins over anything inherited from the
# shell at process startup (avoids stale credentials lingering in the env).
load_dotenv(override=True)

from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Body, Form
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config.settings import get_settings, Settings
from app.config.prompt import SYSTEM_PROMPT
from app.config.version import VERSION
from app.memory.manager import MemoryManager
from app.memory.fact_extractor import extract_facts
from app.attachments.store import AttachmentStore
from app.conversation.manager import ConversationManager
from app.prompt.builder import PromptBuilder
from app.context.manager import ContextWindowManager
from app.memory.retrieval import KeywordRetriever
from app.memory.hybrid_retriever import HybridRetriever
from app.memory.vector_retriever import VectorRetriever
from app.memory.conversation_store import ConversationVectorStore
from app.models.switcher import ModelSwitcher
from app.models.router import TaskType
from app.utils.server_manager import ollama_model_names
from app.utils.logging_setup import setup_logging, get_logger
from app.utils.model_selector import _categorize_cloud_models

# Knowledge / RAG subsystem (research assistant).
from app.knowledge.store import PaperStore
from app.knowledge.ingest import ingest_pdf_bytes
from app.knowledge.rag import answer
from app.knowledge.findings import save_finding


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
# Project root = two levels up from app/api/server.py  (app/api -> app -> root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


# --------------------------------------------------------------------------
# Global engine state
# --------------------------------------------------------------------------
class JarvisEngine:
    """Holds the shared, long-lived JARVIS singletons and per-conversation state."""

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

        # Conversation vector store (semantic history search).
        self.conv_store = ConversationVectorStore(
            persist_dir=str(self.settings.paths.chroma_dir),
            ollama_url=self.settings.paths.ollama_url,
            embed_model=self.settings.paths.embed_model,
        )
        if self.conv_store.count() == 0:
            # Best-effort backfill of existing history into the vector store.
            try:
                from app.conversation.manager import ConversationManager as _CM
                default_cm = _CM()
                indexed = self.conv_store.index_history(default_cm.get_all())
                if indexed > 0:
                    get_logger(__name__).info(
                        "Indexed %d exchanges into conversation store", indexed
                    )
            except Exception:  # pragma: no cover - non-fatal
                pass

        # Per-conversation managers, keyed by conversation id.
        self.conversations: dict[str, ConversationManager] = {}

        # Active cancellation event for the currently streaming chat request.
        self._stop_lock = threading.Lock()
        self.stop_requested: bool = False

        # Persistent Attachments Library (files organized into folders/subfolders).
        self.attachments = AttachmentStore(
            attachments_dir=self.settings.paths.attachments_dir
        )

        # Pre-create the default research folder so the UI always has a
        # sensible target for uploads ("ask within a folder").
        try:
            self.attachments.create_folder("Materials Science")
        except ValueError:
            pass  # already exists — fine

        # RAG knowledge base for ingested papers (ChromaDB: jarvis-papers).
        self.papers = PaperStore(
            persist_dir=str(self.settings.paths.chroma_dir),
            ollama_url=self.settings.paths.ollama_url,
            embed_model=self.settings.paths.embed_model,
        )

    # ---- conversation helpers ----
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

    # ---- stop signalling ----
    def request_stop(self) -> None:
        with self._stop_lock:
            self.stop_requested = True

    def clear_stop(self) -> None:
        with self._stop_lock:
            self.stop_requested = False

    def should_stop(self) -> bool:
        with self._stop_lock:
            return self.stop_requested


# --------------------------------------------------------------------------
# Model / settings introspection
# --------------------------------------------------------------------------
def list_models(engine: JarvisEngine) -> list[dict]:
    """Build a frontend-friendly list of selectable models / backends."""
    settings = engine.settings
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
    from app.utils.server_manager import llamacpp_live_models
    live = llamacpp_live_models(settings)
    if live:
        groups.append({
            "provider": "llamacpp",
            "label": "llama.cpp (local server)",
            "requires_key": False,
            "models": [{"id": f"model:{m['key']}", "name": m["name"], "backend": "llamacpp"} for m in live],
        })

    # Cloud providers — show configured provider models by provider, deduped by model name.
    cloud_providers = [
        ("openrouter", "OpenRouter", "OPENROUTER_API_KEY"),
        ("together", "Together AI", "TOGETHER_API_KEY"),
        ("cerebras", "Cerebras", "CEREBRAS_API_KEY"),
        ("openai", "OpenAI", "OPENAI_API_KEY"),
        ("anthropic", "Anthropic", "ANTHROPIC_API_KEY"),
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

    # "All models" — live catalog browse for providers that expose one. This
    # lets the user pick ANY model the provider serves without hardcoding it in
    # config. OpenRouter is the primary one; we show a curated default and a
    # link to the full catalog (fetched client-side via /api/models/catalog).
    if bool(os.environ.get("OPENROUTER_API_KEY", "")):
        # One sane default so the user always has a pre-selected choice.
        default_or_model = next(
            (settings.models[k].name for k in cloud.get("openrouter", [])
             if "free" in settings.models[k].name.lower()),
            "anthropic/claude-3.5-sonnet",
        )

        # Pick a live free OpenRouter model if possible; otherwise fall back to
        # the configured default or a safe shared model.
        default_free_model = default_or_model
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
            "key_set": bool(os.environ.get("OPENROUTER_API_KEY", "")),
            "dynamic": True,
            "models": [],
        })

    # Dynamic catalog providers (live model browsing with API key)
    # These are shown regardless of whether OPENROUTER_API_KEY is set
    dynamic_providers = [
        ("google", "Google", "GOOGLE_API_KEY"),
        ("grok", "Grok", "XAI_API_KEY"),
        ("groq", "Groq", "GROQ_API_KEY"),
        ("sambanova", "SambaNova", "SAMBANOVA_API_KEY"),
        ("nvidia", "NVIDIA NIM", "NVIDIA_API_KEY"),
        ("together", "Together AI", "TOGETHER_API_KEY"),
        ("cerebras", "Cerebras", "CEREBRAS_API_KEY"),
        ("openai", "OpenAI", "OPENAI_API_KEY"),
        ("anthropic", "Anthropic", "ANTHROPIC_API_KEY"),
    ]
    for provider, label, env_var in dynamic_providers:
        key_set = bool(os.environ.get(env_var, ""))
        groups.append({
            "provider": provider,
            "label": f"{label} — live catalog",
            "requires_key": True,
            "key_env": env_var,
            "key_set": key_set,
            "dynamic": True,
            "models": [],
        })

    # Always-available configured models are already surfaced per provider.

    return groups


def apply_model_selection(engine: JarvisEngine, model_id: str) -> dict:
    """Select a model (or ollama model) on the switcher. Returns status dict."""
    switcher = engine.switcher
    # Allow selecting a pre-built router/profile by name (e.g. 'omni').
    if model_id in switcher._routers:
        ok = switcher.switch(model_id)
        if ok:
            return {"ok": True, "active": switcher.active_profile, "name": model_id}
        return {"ok": False, "error": f"Profile '{model_id}' is not usable"}
    if model_id.startswith("ollama:"):
        model_name = model_id[len("ollama:"):]
        # Build an ad-hoc single-model router for the Ollama model.
        from app.models.ollama_client import OllamaClient
        from app.models.router import ModelRouter as _Router
        try:
            client = OllamaClient(
                model=model_name,
                base_url=engine.settings.paths.ollama_url,
                role="general",
            )
        except Exception as e:  # pragma: no cover - depends on environment
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


def apply_dynamic_selection(engine: JarvisEngine, backend: str, model_id: str, user_keys: dict = None) -> dict:
    """Build an on-the-fly client for ANY provider model id and route to it.

    ``backend`` is "openrouter" / "grok" / "google". The provider routes to
    whatever ``model_id`` we pass, so no config entry is required. Returns a
    status dict like ``apply_model_selection``.
    """
    key_env = {
        "openrouter": "OPENROUTER_API_KEY",
        "grok": "XAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "together": "TOGETHER_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }.get(backend)
    if not key_env:
        return {"ok": False, "error": f"Unknown backend '{backend}'"}
    
    # ONLY use user-provided key from headers
    if user_keys and key_env in user_keys and user_keys[key_env]:
        api_key = user_keys[key_env]
    else:
        return {"ok": False, "error": f"{key_env} is not set — add it in Settings"}
    
    ok = engine.switcher.switch_to_dynamic_model(backend, model_id, api_key)
    if ok:
        return {
            "ok": True,
            "active": engine.switcher.active_profile,
            "name": model_id,
            "dynamic": True,
        }
    return {"ok": False, "error": f"Could not load {backend} model '{model_id}' (key missing?)"}


def apply_settings(engine: JarvisEngine, payload: dict) -> dict:
    """Rebuild switcher clients.
    
    In Phase 1, we no longer persist user keys to .env or os.environ 
    globally via this endpoint. The keys are sent in request headers.
    This endpoint is now mainly for rebuilding the switcher or 
    updating dev key usage.
    """
    use_dev = bool(payload.get("use_developer_keys", False))
    
    # Rebuild switcher clients so new settings take effect.
    engine.switcher = ModelSwitcher(engine.settings)
    return {"ok": True, "use_developer_keys": use_dev}


def _write_env_var(env_path: Path, key: str, value: str) -> None:
    """Append or replace a KEY=VALUE line in the .env file (non-destructive).

    Any existing line for the same key is removed first, so the file never
    accumulates duplicate KEY=VALUE entries (which would make it ambiguous
    which credential is actually used).
    """
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()
    filtered = [ln for ln in lines if not ln.strip().startswith(f"{key}=")]
    filtered.append(f"{key}={value}")
    env_path.write_text("\n".join(filtered) + "\n")


# --------------------------------------------------------------------------
# Chat pipeline (mirrors app/main.py but per-conversation + streamable)
# --------------------------------------------------------------------------
def build_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# Upper bound on how much extracted text we inject into a single chat turn.
# Research papers can be huge; the model's context window is the real limit,
# but we cap per-file text here so one massive PDF can't blow the whole prompt.
_MAX_ATTACHMENT_TEXT = 120_000


def _looks_like_text(name: str, mime: str) -> bool:
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
    """Turn an uploaded file's bytes into readable text for the model.

    * Text-like files are decoded as UTF-8.
    * PDFs are run through ``pdftotext`` (poppler) when available, else a
      minimal pure-Python text scrape as a fallback.
    * DOCX is extracted via ``python-docx`` when available.
    * Anything else (images, zip, binary) is reported as unreadable so the
      model isn't fed garbage.
    """
    name = name or "file"
    if _looks_like_text(name, mime):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="replace")

    low = name.lower()
    if low.endswith(".pdf"):
        # Prefer the system pdftotext binary (poppler) — best quality, no deps.
        try:
            import subprocess
            out = subprocess.run(
                ["pdftotext", "-", "-"], input=raw, capture_output=True, timeout=30
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.decode("utf-8", errors="replace")
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            pass
        # If pdftotext did not return usable text, prefer OCR using
        # pdftoppm + tesseract. This handles scanned/image-only PDFs.
        try:
            import tempfile
            import glob

            with tempfile.TemporaryDirectory() as td:
                pdf_path = Path(td) / "input.pdf"
                pdf_path.write_bytes(raw)
                # Convert all pages to PNGs (prefix 'page')
                subprocess.run(["pdftoppm", "-png", str(pdf_path), str(Path(td) / "page")], check=True, timeout=60)
                ocr_texts = []
                for img in sorted(glob.glob(str(Path(td) / "page-*.png"))):
                    try:
                        p = subprocess.run(["tesseract", img, "stdout", "-l", "eng"], capture_output=True, timeout=30)
                        if p.returncode == 0 and p.stdout.strip():
                            ocr_texts.append(p.stdout.decode("utf-8", errors="replace"))
                    except Exception:
                        continue
                if ocr_texts:
                    return "[PDF — OCR text]\n" + "\n\n".join(ocr_texts)
        except Exception:
            pass

        return ("[PDF file — text extraction unavailable. Install poppler "
                "(`apt install poppler-utils`) or a Python PDF library to read this file, or enable Tesseract for OCR.]")

    if low.endswith(".docx"):
        try:
            import docx  # python-docx
            import io
            d = docx.Document(io.BytesIO(raw))
            return "\n".join(p.text for p in d.paragraphs if p.text)
        except Exception:
            return "[DOCX file — install `python-docx` to read this file's text.]"

    # Binary / unsupported: don't feed garbage to the model.
    return f"[{name} — binary file ({len(raw)} bytes); text content not readable.]"


def run_chat_stream(engine: JarvisEngine, conv_id: str, user_text: str, attachments=None):
    """Generator yielding SSE chunks for a single chat turn.

    Yields ``event: token`` lines for streamed model output, plus ``event:
    done`` / ``event: error`` bookends. Honors engine.should_stop() so the
    frontend's Stop button can abort mid-generation.

    ``attachments`` is an optional list of {name, content} dicts sent inline
    with the chat request (the preferred path); the legacy global buffer is no
    longer used.
    """
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

    import queue as _queue

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


def apply_dynamic_selection(engine: JarvisEngine, backend: str, model_id: str, user_keys: dict = None) -> dict:
    """Build an on-the-fly client for ANY provider model id and route to it.

    ``backend" is "openrouter" / "grok" / "google" / "together" / "cerebras" / "openai" / "anthropic". The provider routes to
    whatever ``model_id`` we pass, so no config entry is required. Returns a
    status dict like ``apply_model_selection``.
    """
    key_env = {
        "openrouter": "OPENROUTER_API_KEY",
        "grok": "XAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "together": "TOGETHER_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }.get(backend)
    if not key_env:
        return {"ok": False, "error": f"Unknown backend '{backend}'"}
    
    # ONLY use user-provided key from headers
    if user_keys and key_env in user_keys and user_keys[key_env]:
        api_key = user_keys[key_env]
    else:
        return {"ok": False, "error": f"{key_env} is not set — add it in Settings"}
    
    ok = engine.switcher.switch_to_dynamic_model(backend, model_id, api_key)
    if ok:
        return {
            "ok": True,
            "active": engine.switcher.active_profile,
            "name": model_id,
            "dynamic": True,
        }
    return {"ok": False, "error": f"Could not load {backend} model '{model_id}' (key missing?)"}


# --------------------------------------------------------------------------
# App factory
# --------------------------------------------------------------------------
def create_app() -> FastAPI:
    setup_logging()
    logger = get_logger(__name__)

    engine = JarvisEngine()

    app = FastAPI(title="JARVIS Web UI", version=VERSION)
    # Expose the engine for tests / introspection (e.g. swap stores/clients).
    app.state.engine = engine

    def _remote_health_check(url: str | None, timeout: int = 5) -> dict:
        """Check a remote OCR service for basic health.

        Tries a GET on the service's /health endpoint (derived from the
        configured URL) using `requests` if available, else falls back to
        urllib. Returns a dict with `ok` boolean and optional details.
        """
        if not url:
            return {"ok": False, "error": "remote_ocr_url not configured"}
        try:
            # prefer requests for simplicity
            import requests
            from urllib.parse import urlparse, urlunparse

            p = urlparse(url)
            base = urlunparse((p.scheme, p.netloc, "", "", "", ""))
            health_url = base.rstrip("/") + "/health"
            try:
                r = requests.get(health_url, timeout=timeout)
                if r.status_code == 200:
                    # try parse json
                    content = None
                    try:
                        content = r.json()
                    except Exception:
                        content = r.text
                    return {"ok": True, "status_code": r.status_code, "detail": content}
            except Exception:
                pass
            # fallback: try the configured URL directly
            r2 = requests.get(url, timeout=timeout)
            if r2.status_code == 200:
                return {"ok": True, "status_code": r2.status_code}
            return {"ok": False, "status_code": r2.status_code}
        except Exception:
            # urllib fallback
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


    @app.middleware("http")
    async def extract_api_keys(request: Request, call_next):
        """Extract API keys from X-API-Key headers and put them in request state."""
        headers = request.headers
        keys = {}
        for k, v in headers.items():
            if k.lower().startswith("x-api-key-"):
                env_var = k[10:].upper().replace("-", "_")
                keys[env_var] = v
        request.state.user_keys = keys
        response = await call_next(request)
        return response

    # ---- models ----
    @app.get("/api/models")
    def get_models():
        return {
            "active_profile": engine.switcher.active_profile,
            "groups": list_models(engine),
            "version": VERSION,
        }

    @app.post("/api/models/select")
    @app.post("/api/models/select")
    def select_model(payload: dict = Body(...), request: Request = None):
        model_id = payload.get("model_id")
        if not model_id:
            raise HTTPException(400, "model_id required")
        # Dynamic selection: {"model_id": "dyn", "backend": "...", "model": "..."}
        if model_id == "dyn" or payload.get("dynamic"):
            backend = payload.get("backend")
            model = payload.get("model")
            if not backend or not model:
                raise HTTPException(400, "backend and model required for dynamic selection")
            user_keys = request.state.user_keys if request else {}
            result = apply_dynamic_selection(engine, backend, model, user_keys)
            if not result.get("ok"):
                raise HTTPException(400, result.get("error", "selection failed"))
            return result
        result = apply_model_selection(engine, model_id)
        if not result.get("ok"):
            raise HTTPException(400, result.get("error", "selection failed"))
        return result

    @app.get("/api/models/catalog")
    def model_catalog(provider: str = "openrouter", query: str = "", limit: int = 50, free_only: bool = False):
        """Live catalog of every model a provider serves."""
        catalog_functions = {
            "openrouter": "app.utils.openrouter_catalog.search_openrouter_models",
            "together": "app.utils.together_catalog.search_together_models",
            "cerebras": "app.utils.cerebras_catalog.search_cerebras_models",
            "openai": "app.utils.openai_catalog.search_openai_models",
            "anthropic": "app.utils.anthropic_catalog.search_anthropic_models",
            "google": "app.utils.provider_catalog.search_google_models",
            "grok": "app.utils.provider_catalog.search_grok_models",
            "groq": "app.utils.provider_catalog.search_groq_models",
            "sambanova": "app.utils.provider_catalog.search_sambanova_models",
            "nvidia": "app.utils.provider_catalog.search_nvidia_models",
            "mistral": "app.utils.provider_catalog.search_mistral_models",
            "cohere": "app.utils.provider_catalog.search_cohere_models",
            "github": "app.utils.provider_catalog.search_github_models",
            "cloudflare": "app.utils.provider_catalog.search_cloudflare_models",
            "zhipu": "app.utils.provider_catalog.search_zhipu_models",
            "huggingface": "app.utils.provider_catalog.search_huggingface_models",
        }
        
        if provider not in catalog_functions:
            raise HTTPException(400, f"Provider '{provider}' catalog not supported. Available: {list(catalog_functions.keys())}")
        
        # Dynamic import
        module_path, func_name = catalog_functions[provider].rsplit(".", 1)
        module = __import__(module_path, fromlist=[func_name])
        search_func = getattr(module, func_name)
        
        models = search_func(query, limit=limit, free_only=free_only)
        return {"provider": provider, "count": len(models), "models": models, "free_only": free_only}


    @app.get("/api/models/info")
    def model_info(provider: str, model: str):
        """Get detailed metadata for a specific model."""
        catalog_functions = {
            "openrouter": "app.utils.openrouter_catalog.search_openrouter_models",
            "together": "app.utils.together_catalog.search_together_models",
            "cerebras": "app.utils.cerebras_catalog.search_cerebras_models",
            "openai": "app.utils.openai_catalog.search_openai_models",
            "anthropic": "app.utils.anthropic_catalog.search_anthropic_models",
            "google": "app.utils.provider_catalog.search_google_models",
            "grok": "app.utils.provider_catalog.search_grok_models",
            "groq": "app.utils.provider_catalog.search_groq_models",
            "sambanova": "app.utils.provider_catalog.search_sambanova_models",
            "nvidia": "app.utils.provider_catalog.search_nvidia_models",
            "mistral": "app.utils.provider_catalog.search_mistral_models",
            "cohere": "app.utils.provider_catalog.search_cohere_models",
            "github": "app.utils.provider_catalog.search_github_models",
            "cloudflare": "app.utils.provider_catalog.search_cloudflare_models",
            "zhipu": "app.utils.provider_catalog.search_zhipu_models",
            "huggingface": "app.utils.provider_catalog.search_huggingface_models",
        }
        
        if provider not in catalog_functions:
            raise HTTPException(400, f"Provider '{provider}' not supported")
        
        module_path, func_name = catalog_functions[provider].rsplit(".", 1)
        module = __import__(module_path, fromlist=[func_name])
        search_func = getattr(module, func_name)
        
        # Search for exact model match
        models = search_func(model, limit=5, free_only=False)
        exact = next((m for m in models if m.get("id") == model), None)
        if not exact and models:
            exact = models[0]  # fallback to first match
        
        if not exact:
            raise HTTPException(404, f"Model '{model}' not found in {provider}")
        
        return {"provider": provider, "model": exact}


    @app.get("/api/models/capabilities")
    def capabilities_matrix():
        """Provider capability comparison matrix."""
        from app.provider_registry import get_provider_registry
        reg = get_provider_registry()
        providers = reg.get_all_providers(force_refresh=False)
        
        matrix = []
        for p in providers:
            caps = p.get("capabilities", {})
            matrix.append({
                "provider": p["key"],
                "name": p["name"],
                "openai_compatible": caps.get("is_openai_compatible", False),
                "reasoning": caps.get("is_reasoning_capable", False),
                "code_generation": caps.get("is_code_generation_capable", False),
                "stem": caps.get("is_stem_capable", False),
                "documentation": caps.get("is_documentation_capable", False),
                "realtime": caps.get("is_realtime_capable", False),
                "has_free_models": caps.get("has_free_models", False),
                "context_window": caps.get("context_window_size", 0),
                "max_output": caps.get("max_output_tokens", 0),
                "status": p.get("status", "unknown"),
                "has_key": p.get("has_api_key", False),
            })
        
        return {"providers": matrix}


    # ---- settings ----
    @app.get("/api/settings")
    def get_settings_endpoint():
        settings = engine.settings
        return {
            "use_developer_keys": True,  # informational default
            "providers": {
                "google": bool(os.environ.get("GOOGLE_API_KEY", "")),
                "grok": bool(os.environ.get("XAI_API_KEY", "")),
                "openrouter": bool(os.environ.get("OPENROUTER_API_KEY", "")),
                "openai": bool(os.environ.get("OPENAI_API_KEY", "")),
            },
            "context_max_tokens": settings.context.max_tokens,
            "memory_retrieval_limit": settings.memory.retrieval_limit,
        }

    @app.post("/api/settings")
    def post_settings(payload: dict = Body(...)):
        return apply_settings(engine, payload)

    # ---- conversations ----
    @app.get("/api/conversations")
    def get_conversations():
        return {"conversations": engine.list_conversations()}

    @app.post("/api/conversations")
    def create_conversation(payload: dict = Body(default={})):
        cid = payload.get("id") or uuid.uuid4().hex
        engine.get_or_create_conversation(cid)
        return {"id": cid}

    @app.get("/api/conversations/{conv_id}")
    def get_conversation(conv_id: str):
        cm = engine.get_or_create_conversation(conv_id)
        return {
            "id": conv_id,
            "messages": [m.to_dict() for m in cm.get_all()],
        }

    @app.delete("/api/conversations/{conv_id}")
    def delete_conversation(conv_id: str):
        engine.conversations.pop(conv_id, None)
        p = engine.settings.paths.conversations_dir / f"{conv_id}.json"
        if p.exists():
            p.unlink()
        return {"ok": True}

    @app.get("/api/conversations/{conv_id}/search")
    def search_conversation(conv_id: str, q: str = ""):
        """Search messages within a conversation."""
        cm = engine.get_or_create_conversation(conv_id)
        return {"results": cm.search_messages(q)}

    @app.post("/api/conversations/{conv_id}/pin")
    def pin_message(conv_id: str, payload: dict = Body(default={})):
        """Toggle pin status of a message."""
        index = payload.get("index")
        if index is None:
            raise HTTPException(400, "Missing message index")
        cm = engine.get_or_create_conversation(conv_id)
        pinned = cm.toggle_pin(index)
        return {"ok": True, "pinned": pinned}

    @app.get("/api/conversations/{conv_id}/pinned")
    def get_pinned_messages(conv_id: str):
        """Get all pinned messages in a conversation."""
        cm = engine.get_or_create_conversation(conv_id)
        return {"pinned": [m.to_dict() for m in cm.get_pinned_messages()]}

    # ---- chat (SSE streaming) ----
    @app.post("/api/chat")
    async def chat(request: Request):
        # Accept EITHER application/json (text-only) OR multipart/form-data
        # (with inline attachment files). We read the raw request ourselves
        # because mixing a JSON ``Body`` with ``Form``/``File`` parameters makes
        # FastAPI reject the JSON body outright, which previously broke every
        # text-only message.
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

        conv_id = conv_id or uuid.uuid4().hex

        if not message:
            raise HTTPException(400, "message required")

        # Use a thread executor so the blocking JARVIS pipeline doesn't block
        # the event loop, and so we can stream incrementally.
        async def event_gen():
            loop = asyncio.get_event_loop()
            # Run the generator in a thread, pushing events to a queue.
            queue: asyncio.Queue = asyncio.Queue()

            def producer():
                try:
                    for chunk in run_chat_stream(engine, conv_id, message, atts):
                        asyncio.run_coroutine_threadsafe(queue.put(chunk), loop)
                except Exception as e:  # pragma: no cover
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

    @app.post("/api/stop")
    def stop():
        engine.request_stop()
        return {"ok": True}

    # ---- memories (read-only view) ----
    @app.get("/api/memories")
    def get_memories():
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

    # ---- attachments library (persistent files organized into folders) ----
    @app.get("/api/attachments/tree")
    def attachments_tree():
        return {"tree": engine.attachments.list_tree()}

    @app.post("/api/attachments/folders")
    def create_folder(payload: dict = Body(default={})):
        try:
            return engine.attachments.create_folder(payload.get("path", ""))
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.put("/api/attachments/folders")
    def rename_folder(payload: dict = Body(default={})):
        try:
            return engine.attachments.rename_folder(
                payload.get("old_path", ""), payload.get("new_path", ""))
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.delete("/api/attachments/folders")
    def delete_folder(path: str = "", recursive: bool = False):
        try:
            return engine.attachments.delete_folder(path, recursive=recursive)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/api/attachments/files")
    def list_attachment_files(folder: str = ""):
        return {"files": engine.attachments.list_files(folder)}

    @app.post("/api/attachments/files")
    async def upload_attachment_file(
        folder: str = Form(""),
        file: UploadFile = File(...),
    ):
        raw = await file.read()
        if len(raw) > 50 * 1024 * 1024:
            raise HTTPException(400, "File too large (50MB max)")
        try:
            meta = engine.attachments.save_file(
                raw, file.filename or "upload", folder, file.content_type or "application/octet-stream")
        except ValueError as e:
            raise HTTPException(400, str(e))
        return meta

    @app.get("/api/attachments/files/{file_id}")
    def get_attachment_file(file_id: str):
        try:
            data, fm = engine.attachments.read_file(file_id)
        except FileNotFoundError:
            raise HTTPException(404, "File not found")
        from fastapi.responses import Response
        return Response(content=data, media_type=fm.mime or "application/octet-stream",
                         headers={"Content-Disposition": f'inline; filename="{fm.name}"'})

    @app.put("/api/attachments/files/{file_id}")
    def move_attachment_file(file_id: str, payload: dict = Body(default={})):
        try:
            return engine.attachments.move_file(file_id, payload.get("folder", ""))
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(400, str(e))

    @app.delete("/api/attachments/files/{file_id}")
    def delete_attachment_file(file_id: str):
        try:
            return engine.attachments.delete_file(file_id)
        except FileNotFoundError:
            raise HTTPException(404, "File not found")

    @app.get("/api/attachments/search")
    def search_attachment_files(query: str = ""):
        return {"files": engine.attachments.search(query)}

    # ---- research papers (RAG knowledge base) ----
    @app.get("/api/papers/folders")
    def list_paper_folders():
        """Folder names available for scoping ingestion/queries.

        Reuses the Attachments Library folder system so papers live alongside
        other uploaded files in the same folders.
        """
        return {"folders": engine.attachments.list_folders()}

    @app.get("/api/papers")
    def list_papers(folder: str = ""):
        docs = engine.papers.list_documents(folder=folder or None)
        return {"documents": docs, "count": len(docs)}

    @app.post("/api/papers/ingest")
    async def ingest_paper(
        file: UploadFile = File(...),
        folder: str = Form("Materials Science"),
        title: str = Form(""),
    ):
        """Upload + ingest a PDF into the knowledge base.

        The PDF bytes are also saved into the Attachments Library under
        ``folder`` (default "Materials Science") so it appears in the file
        browser and can be re-attached to a chat. Returns ingestion summary.
        """
        raw = await file.read()
        if not raw:
            raise HTTPException(400, "Empty file")
        if len(raw) > 100 * 1024 * 1024:
            raise HTTPException(400, "PDF too large (100MB max)")
        fname = os.path.basename(file.filename or "paper.pdf")
        if not fname.lower().endswith(".pdf"):
            raise HTTPException(400, "Only PDF files are supported")

        # If configured to use remote OCR, pre-check the remote service.
        if engine.settings.knowledge.ocr_engine and engine.settings.knowledge.ocr_engine.lower() == "remote":
            url = engine.settings.knowledge.remote_ocr_url
            hc = _remote_health_check(url)
            if not hc.get("ok"):
                raise HTTPException(503, f"Remote OCR not available: {hc.get('error') or hc.get('status_code')}")

        try:
            result = ingest_pdf_bytes(
                pdf_bytes=raw,
                filename=fname,
                store=engine.papers,
                title=title or "",
                folder=folder or "",
            )
        except Exception as e:
            raise HTTPException(500, f"Ingestion failed: {e}")

        # Persist the original PDF in the Attachments Library folder too.
        try:
            engine.attachments.save_file(
                raw, fname, folder or "", file.content_type or "application/pdf"
            )
        except Exception as e:  # non-fatal — ingestion already succeeded
            logger.warning("Could not save PDF to attachments: %s", e)

        return result

    @app.post("/api/papers/query")
    def query_papers(payload: dict = Body(default={})):
        """Ask a question across ingested papers (optionally within a folder)."""
        query = (payload.get("query") or "").strip()
        if not query:
            raise HTTPException(400, "query required")
        folder = payload.get("folder") or None
        limit = int(payload.get("limit") or engine.settings.knowledge.retrieval_limit)

        try:
            selected_model = engine.switcher.router.default_model
            if selected_model is None:
                raise HTTPException(400, "No active model. Pick one in Settings.")
            result = answer(
                query=query,
                model_client=selected_model,
                store=engine.papers,
                limit=limit,
                folder=folder,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"RAG query failed: {e}")

        return {
            "answer": result.answer,
            "sources": result.sources,
        }

    @app.post("/api/papers/findings")
    def save_paper_finding(payload: dict = Body(default={})):
        """Save a research finding into long-term memory."""
        text = (payload.get("text") or "").strip()
        if not text:
            raise HTTPException(400, "text required")
        try:
            memory = save_finding(
                engine.memory,
                text=text,
                source_meta=payload.get("source_meta") or {},
            )
        except Exception as e:
            raise HTTPException(500, f"Could not save finding: {e}")
        if memory is None:
            raise HTTPException(400, "Finding text was empty")
        return {
            "ok": True,
            "memory_id": memory.id,
            "category": memory.category,
            "memory_type": memory.memory_type,
            "metadata": memory.metadata,
        }

    @app.delete("/api/papers/{doc_id}")
    def delete_paper(doc_id: str):
        removed = engine.papers.clear_document(doc_id)
        # Best-effort: also drop the persisted PDF bytes.
        pdf_path = engine.settings.paths.papers_dir / f"{doc_id}.pdf"
        if pdf_path.exists():
            try:
                pdf_path.unlink()
            except OSError:
                pass
        return {"ok": True, "removed_chunks": removed}

    # ---- static frontend ----
    @app.get("/api/health")
    def health():
        return {"ok": True, "version": VERSION}

    @app.get("/api/ocr/remote_health")
    def ocr_remote_health():
        url = engine.settings.knowledge.remote_ocr_url
        hc = _remote_health_check(url)
        return hc

    @app.get("/api/ocr/local_health")
    def ocr_local_health():
        """Check if local Tesseract OCR is available."""
        import subprocess
        try:
            result = subprocess.run(['tesseract', '--version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.decode('utf-8', errors='replace').split('\n')[0]
                # Get available languages
                lang_result = subprocess.run(['tesseract', '--list-langs'], capture_output=True, timeout=5)
                langs = []
                if lang_result.returncode == 0:
                    langs = lang_result.stdout.decode('utf-8', errors='replace').strip().split('\n')[1:]
                return {
                    "ok": True,
                    "available": True,
                    "engine": "tesseract",
                    "version": version,
                    "languages": langs
                }
            return {"ok": False, "available": False, "error": "tesseract not found"}
        except FileNotFoundError:
            return {"ok": False, "available": False, "error": "tesseract not installed"}
        except Exception as e:
            return {"ok": False, "available": False, "error": str(e)}



    # Serve index.html at "/" and static assets.
    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")

    if FRONTEND_DIR.exists():
        # Serve the SPA, but disable caching of the source assets so a deployed
        # frontend update is picked up immediately (otherwise browsers keep
        # running a stale app.js and the new UI/buttons appear "broken").
        class NoCacheStatic(StaticFiles):
            async def get_response(self, path: str, scope):
                resp = await super().get_response(path, scope)
                resp.headers.update({
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                })
                return resp

        app.mount("/", NoCacheStatic(directory=str(FRONTEND_DIR), html=True), name="static")

    return app


def run(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    import uvicorn
    uvicorn.run("app.api.server:create_app", factory=True, host=host, port=port, reload=reload)


if __name__ == "__main__":
    run()

