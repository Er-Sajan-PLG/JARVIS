"""API routes for the JARVIS web console.

Provides the full vertical slice behind the web UI:

* model catalogue (live, per-provider, with real availability status)
* settings — default model, custom providers, custom models, API keys
* chat execution that honours the selected provider/model
* file store (list / preview / download / delete)
* memory management
* conversation lifecycle

Security: provider credentials live in ``app.adapters.web.settings`` and are
never serialised into a response. Only ``has_key`` booleans cross the wire.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import uuid
from datetime import UTC
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.adapters.security import is_authorized
from app.bootstrap import bootstrap_system

# Load .env file from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

web_router = APIRouter(prefix="/api", tags=["JARVIS Web API"])

UPLOAD_DIR = _PROJECT_ROOT / "data" / "uploads"

TEXT_SUFFIXES = (
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".log",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sh",
    ".bash",
    ".sql",
    ".xml",
    ".rst",
)


def _validate_api_key(request: Request) -> bool:
    authorization = request.headers.get("authorization")
    x_api_key = request.headers.get("x-api-key")
    if is_authorized(authorization=authorization, x_api_key=x_api_key):
        return True
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


# ── Model catalogue ──────────────────────────────────────────────────────────


def _agy_provider_entry() -> dict[str, Any] | None:
    """The AGY (Google AI Pro via Antigravity CLI) pseudo-provider."""
    try:
        from app.adapters.integrations.agy import get_models, is_available

        if not is_available():
            return {
                "key": "agy",
                "name": "AGY (Google AI Pro)",
                "status": "unavailable",
                "has_key": False,
                "is_local": True,
                "model_count": 0,
                "models": [],
                "categories": [],
                "is_openai_compatible": False,
                "free_models_available": False,
                "error": "AGY CLI not found on PATH",
            }
        models = get_models()
        return {
            "key": "agy",
            "name": "AGY (Google AI Pro)",
            "status": "available" if models else "error",
            "has_key": True,
            "is_local": True,
            "model_count": len(models),
            "models": models,
            "categories": ["reasoning", "general"],
            "is_openai_compatible": False,
            "free_models_available": False,
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("AGY provider probe failed: %s", exc)
        return None


@web_router.get("/models")
async def list_models(refresh: bool = False) -> dict[str, Any]:
    """Every provider with its LIVE models and honest availability status."""
    from app.adapters.web.settings import get_custom_models, get_custom_providers_with_keys
    from app.utils.provider_catalog import get_all_providers

    providers = get_all_providers(force_refresh=refresh)

    agy = _agy_provider_entry()
    if agy is not None:
        providers.insert(0, agy)

    for cp in get_custom_providers_with_keys():
        # Provider-level defaults apply to models that don't declare their own.
        p_ctx = int(cp.get("context_length") or 0)
        p_caps = list(cp.get("capabilities") or [])
        models = [
            {
                "id": m.get("id", ""),
                "name": m.get("name") or m.get("id", ""),
                "description": m.get("description", ""),
                "context_length": m.get("context_length") or p_ctx,
                "capabilities": list(m.get("capabilities") or p_caps),
                "pricing": m.get("pricing", {}),
                "is_custom": True,
            }
            for m in cp.get("models", [])
            if m.get("id")
        ]
        providers.append(
            {
                "key": cp["key"],
                "name": cp.get("name") or cp["key"],
                "status": "available" if models else "no_models",
                "has_key": bool(cp.get("api_key")),
                "is_local": False,
                "is_custom": True,
                "base_url": cp.get("base_url", ""),
                "context_length": p_ctx,
                "capabilities": p_caps,
                "model_count": len(models),
                "models": models,
                "categories": ["custom"],
                "is_openai_compatible": True,
                "free_models_available": False,
            }
        )

    # Hand-added models attach to whichever provider they name.
    by_key = {p["key"]: p for p in providers}
    for m in get_custom_models():
        target = by_key.get(m.get("provider", ""))
        if target is None:
            continue
        if any(x.get("id") == m["id"] for x in target["models"]):
            continue
        target["models"].append(
            {
                "id": m["id"],
                "name": m.get("name") or m["id"],
                "description": m.get("description", ""),
                "context_length": m.get("context_length", 0),
                "pricing": m.get("pricing", {}),
                "capabilities": m.get("capabilities", []),
                "is_custom": True,
            }
        )
        target["model_count"] = len(target["models"])

    from app.adapters.web.settings import get_hidden_models

    hidden = set(get_hidden_models())
    for p in providers:
        p["models"] = [m for m in p["models"] if f"{p['key']}:{m.get('id')}" not in hidden]
        p["model_count"] = len(p["models"])

    return {"providers": providers}


# ── Default model ────────────────────────────────────────────────────────────


@web_router.get("/settings/default")
async def get_default() -> dict[str, Any]:
    from app.adapters.web.settings import get_default

    return {"default": get_default()}


@web_router.post("/settings/default")
async def set_default(body: dict[str, Any]) -> dict[str, Any]:
    from app.adapters.web.settings import set_default

    provider = (body.get("provider") or "").strip()
    model = (body.get("model") or "").strip()
    if not provider or not model:
        raise HTTPException(status_code=400, detail="provider and model are required")
    return {"success": True, "default": set_default(provider, model)}


# ── Custom providers ─────────────────────────────────────────────────────────


@web_router.get("/settings/providers")
async def list_custom_providers() -> dict[str, Any]:
    from app.adapters.web.settings import get_custom_providers

    return {"providers": get_custom_providers()}


@web_router.post("/settings/providers")
async def add_custom_provider(body: dict[str, Any]) -> dict[str, Any]:
    from app.adapters.web.settings import add_custom_provider

    try:
        record = add_custom_provider(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "provider": record}


@web_router.delete("/settings/providers/{key}")
async def delete_custom_provider(key: str) -> dict[str, Any]:
    from app.adapters.web.settings import delete_custom_provider

    return {"success": delete_custom_provider(key)}


@web_router.post("/settings/providers/fetch-models")
async def fetch_provider_models(body: dict[str, Any]) -> dict[str, Any]:
    """Probe an OpenAI-compatible endpoint's /models for live discovery."""
    import httpx

    base_url = (body.get("base_url") or "").rstrip("/")
    api_key = body.get("api_key") or ""

    if not base_url:
        raise HTTPException(status_code=400, detail="base_url is required")
    if api_key in ("", "••••••••"):
        # Fall back to whatever is already stored for this provider.
        from app.adapters.web.settings import get_custom_providers_with_keys

        for cp in get_custom_providers_with_keys():
            if cp.get("base_url", "").rstrip("/") == base_url:
                api_key = cp.get("api_key", "")
                break

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{base_url}/models", headers=headers)
    except Exception as exc:  # noqa: BLE001
        return {"models": [], "error": f"Could not reach {base_url}: {exc}"}

    if resp.status_code != 200:
        return {
            "models": [],
            "error": f"Provider returned HTTP {resp.status_code}. Check the base URL and API key.",
        }

    try:
        payload = resp.json()
    except Exception:  # noqa: BLE001
        return {"models": [], "error": "Provider did not return JSON"}

    raw = payload.get("data") if isinstance(payload, dict) else None
    if raw is None and isinstance(payload, list):
        raw = payload
    if not isinstance(raw, list):
        return {"models": [], "error": "Unrecognised model list format"}

    models = []
    for item in raw:
        if isinstance(item, str):
            models.append(
                {"id": item, "name": item, "description": "", "context_length": 0, "pricing": {}}
            )
            continue
        if not isinstance(item, dict):
            continue
        model_id = item.get("id") or item.get("name") or ""
        if not model_id:
            continue
        models.append(
            {
                "id": model_id,
                "name": item.get("name") or model_id,
                "description": item.get("description", ""),
                "context_length": item.get("context_length") or item.get("context_window") or 0,
                "pricing": item.get("pricing") or {},
            }
        )

    return {"models": models, "error": None if models else "Provider reported no models"}


# ── Custom models ────────────────────────────────────────────────────────────


@web_router.get("/settings/models")
async def list_custom_models() -> dict[str, Any]:
    from app.adapters.web.settings import get_custom_models, get_hidden_models

    return {"models": get_custom_models(), "hidden": get_hidden_models()}


@web_router.post("/settings/models")
async def add_custom_model(body: dict[str, Any]) -> dict[str, Any]:
    from app.adapters.web.settings import add_custom_model

    try:
        record = add_custom_model(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "model": record}


@web_router.delete("/settings/models/{provider}/{model_id:path}")
async def delete_custom_model(provider: str, model_id: str) -> dict[str, Any]:
    from app.adapters.web.settings import delete_custom_model

    return {"success": delete_custom_model(provider, model_id)}


@web_router.post("/settings/models/hide")
async def hide_model(body: dict[str, Any]) -> dict[str, Any]:
    """Toggle a model's visibility in the catalogue."""
    from app.adapters.web.settings import toggle_hidden_model

    provider = body.get("provider", "")
    model_id = body.get("id", "")
    if not provider or not model_id:
        raise HTTPException(status_code=400, detail="provider and id are required")
    return {"hidden": toggle_hidden_model(provider, model_id)}


# ── API keys ─────────────────────────────────────────────────────────────────


@web_router.get("/settings/api-keys")
async def get_api_keys() -> dict[str, Any]:
    """Which providers have a credential configured. Values are never sent."""
    from app.adapters.web.settings import get_api_key_status

    stored = get_api_key_status()
    env_available = {
        "openrouter": "OPENROUTER_API_KEY",
        "google": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "cohere": "COHERE_API_KEY",
        "huggingface": "HF_TOKEN",
        "nvidia": "NVIDIA_API_KEY",
        "github": "GITHUB_TOKEN",
        "cloudflare": "CLOUDFLARE_API_TOKEN",
        "zhipu": "ZHIPU_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "together": "TOGETHER_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "singularity": "SINGULARITY_API_KEY",
    }
    return {
        "keys": {
            provider: {
                "configured": bool(stored.get(provider)) or bool(os.environ.get(env_var)),
                "source": (
                    "stored"
                    if stored.get(provider)
                    else ("env" if os.environ.get(env_var) else None)
                ),
            }
            for provider, env_var in env_available.items()
        }
    }


@web_router.post("/settings/api-keys")
async def save_api_key(body: dict[str, Any]) -> dict[str, Any]:
    """Store a provider credential. Masked/empty values are ignored."""
    from app.adapters.web.settings import set_api_key

    provider = (body.get("provider") or "").strip()
    value = body.get("key") or ""
    if not provider:
        raise HTTPException(status_code=400, detail="provider is required")
    set_api_key(provider, value)
    return {"success": True}


@web_router.delete("/settings/api-keys/{provider}")
async def delete_api_key(provider: str) -> dict[str, Any]:
    from app.adapters.web.settings import delete_api_key

    return {"success": delete_api_key(provider)}


# ── Chat ─────────────────────────────────────────────────────────────────────


def _extract_content(response: Any) -> tuple[str, Any]:
    """Normalise a provider client's return value."""
    if isinstance(response, dict):
        return response.get("content", "") or "", response.get("tokens_used")
    return getattr(response, "content", "") or "", getattr(response, "tokens_used", None)


@web_router.post("/chat")
async def chat(payload: dict[str, Any]) -> dict[str, Any]:
    container = bootstrap_system()

    message = payload.get("message", "")
    model_info = payload.get("model", {}) or {}
    session_id = payload.get("session_id") or str(uuid.uuid4())
    memory_enabled = payload.get("memory_enabled", True)
    files = payload.get("files", [])
    file_contents = payload.get("file_contents", [])

    if not message and not files:
        raise HTTPException(status_code=400, detail="Message or files required")

    file_context = ""
    for entry in file_contents or []:
        fname = ""
        fcontent = ""
        if isinstance(entry, dict):
            fname = str(entry.get("name", ""))
            fcontent = str(entry.get("content", ""))
        elif isinstance(entry, list | tuple) and len(entry) == 2:
            fname, fcontent = str(entry[0]), str(entry[1])
        else:
            continue
        file_context += f"\n\n[File: {fname}]\n{fcontent}"

    memory_context = ""
    if memory_enabled:
        try:
            memories = await container.memory_service.search_memories(message, limit=3)
            if memories:
                lines = "\n".join(f"- {m.value}" for m in memories)
                memory_context = f"\n\n[Memory Context]\n{lines}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Memory search failed: %s", exc)

    full_message = f"{message}{memory_context}{file_context}"

    provider = model_info.get("provider") or ""
    model_id = model_info.get("id") or ""

    # No explicit model on the request: fall back to the default saved in
    # Settings. Without this the request went out with an empty model id and
    # every provider rejected it ("bad input"), so changing the default in
    # Settings had no effect on chat.
    if not provider or not model_id:
        from app.adapters.web.settings import get_default as _get_default

        saved = _get_default() or {}
        provider = provider or saved.get("provider") or ""
        model_id = model_id or saved.get("model") or ""

    if not model_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "No model selected. Pick one in the composer, or set a default "
                "in Settings → Model → Default Model."
            ),
        )

    try:
        from app.adapters.web.settings import get_custom_providers_with_keys

        response_content: str
        response_tokens: Any

        if provider == "agy":
            from app.adapters.integrations.agy import chat as agy_chat, is_available

            if not is_available():
                raise HTTPException(status_code=503, detail="AGY CLI not found on PATH")
            result = agy_chat(messages=[{"role": "user", "content": full_message}], model=model_id)
            response_content = result.get("content", "")
            response_tokens = result.get("tokens_used")

        else:
            from app.config.settings import ModelConfig
            from app.models.factory import create_client

            custom = {p["key"]: p for p in get_custom_providers_with_keys()}

            if provider in custom:
                cp = custom[provider]
                if not model_id:
                    model_id = next((m.get("id") for m in cp.get("models", []) if m.get("id")), "")
                if not model_id:
                    raise HTTPException(
                        status_code=400, detail=f"No models configured for '{provider}’"
                    )
                config = ModelConfig(
                    name=model_id,
                    role="general",
                    backend="openai",
                    api_key=cp.get("api_key") or "not-needed",
                    base_url=cp.get("base_url", ""),
                )
            else:
                from app.adapters.web.settings import resolve_api_key
                from app.provider_registry import get_provider_registry

                spec = get_provider_registry().get_provider(provider)
                if spec is None:
                    raise HTTPException(status_code=400, detail=f"Unknown provider '{provider}'")

                api_key = resolve_api_key(provider)
                if spec.get("requires_api_key", True) and not api_key:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"No API key configured for '{provider}'. "
                            "Add one in Settings → Model → API Keys."
                        ),
                    )
                config = ModelConfig(
                    name=model_id,
                    role="general",
                    backend=provider,
                    api_key=api_key or "not-needed",
                    base_url=spec.get("api_endpoint") or "",
                )

            client = create_client(config)
            response_content, response_tokens = _extract_content(
                client.generate([{"role": "user", "content": full_message}])
            )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Chat failed: %s", exc, exc_info=True)
        return {"error": f"Model request failed: {exc}"}

    if memory_enabled:
        try:
            # Only the USER's words are stored. The assistant's reply is
            # generated prose, not a fact about the user, and storing it filled
            # the store with near-duplicate paraphrases ("Ah, masala tea..."
            # vs "That's a wonderful choice! Masala tea...") that exact-match
            # dedup can never collapse. The user's turn is the signal.
            await container.memory_service.store_memory(
                key=f"user_{session_id}", value=message, category="conversation"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Memory store failed: %s", exc)

    return {
        "response": response_content,
        "model": model_info,
        "session_id": session_id,
        "tokens_used": response_tokens,
    }


# ── Files ────────────────────────────────────────────────────────────────────


def _classify(name: str, content_type: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf" or content_type == "application/pdf":
        return "pdf"
    image_suffixes = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
    if content_type.startswith("image/") or suffix in image_suffixes:
        return "image"
    if suffix in (".csv", ".tsv", ".xlsx", ".xls"):
        return "spreadsheet"
    if suffix in TEXT_SUFFIXES or content_type.startswith("text/"):
        return "text"
    return "other"


def _read_extracted(path: Path) -> str:
    """Extract text from a stored upload."""
    try:
        content = path.read_bytes()
    except Exception:  # noqa: BLE001
        return ""

    kind = _classify(path.name, mimetypes.guess_type(path.name)[0] or "")
    if kind == "pdf":
        try:
            import pymupdf

            doc = pymupdf.open(stream=content, filetype="pdf")  # type: ignore[no-untyped-call]
            try:
                pages: list[str] = [
                    str(page.get_text())  # type: ignore[no-untyped-call]
                    for page in doc
                ]
            finally:
                doc.close()  # type: ignore[no-untyped-call]
            return "\n".join(pages)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PDF extraction failed for %s: %s", path.name, exc)
            return ""
    if kind in ("text", "spreadsheet"):
        try:
            return content.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return content.decode("latin-1", errors="replace")
    return ""


def _file_record(path: Path) -> dict[str, Any]:
    stat = path.stat()
    # Stored as "<uuid>_<original name>"
    parts = path.name.split("_", 1)
    file_id, original = (parts[0], parts[1]) if len(parts) == 2 else ("", path.name)
    content_type = mimetypes.guess_type(original)[0] or "application/octet-stream"
    return {
        "id": file_id,
        "filename": original,
        "stored_name": path.name,
        "size": stat.st_size,
        "content_type": content_type,
        "kind": _classify(original, content_type),
        "modified": stat.st_mtime,
        "extractable": _classify(original, content_type) in ("pdf", "text", "spreadsheet"),
    }


@web_router.get("/files")
async def list_files(q: str = "", kind: str = "") -> dict[str, Any]:
    """List uploaded files, newest first."""
    if not UPLOAD_DIR.exists():
        return {"files": [], "total": 0}

    records = []
    for path in UPLOAD_DIR.iterdir():
        if not path.is_file() or path.name.startswith("."):
            continue
        try:
            records.append(_file_record(path))
        except Exception as exc:  # noqa: BLE001
            logger.debug("skipping %s: %s", path.name, exc)

    if q:
        needle = q.lower()
        records = [r for r in records if needle in r["filename"].lower()]
    if kind:
        records = [r for r in records if r["kind"] == kind]

    records.sort(key=lambda r: r["modified"], reverse=True)
    return {"files": records, "total": len(records)}


@web_router.get("/files/{file_id}")
async def file_detail(file_id: str) -> dict[str, Any]:
    """Metadata plus extracted text preview for one file."""
    if not UPLOAD_DIR.exists():
        raise HTTPException(status_code=404, detail="File not found")
    for path in UPLOAD_DIR.iterdir():
        if path.is_file() and path.name.split("_", 1)[0] == file_id:
            record = _file_record(path)
            record["preview"] = _read_extracted(path)[:20000]
            return record
    raise HTTPException(status_code=404, detail="File not found")


@web_router.get("/files/{file_id}/download")
async def download_file(file_id: str) -> FileResponse:
    if not UPLOAD_DIR.exists():
        raise HTTPException(status_code=404, detail="File not found")
    for path in UPLOAD_DIR.iterdir():
        if path.is_file() and path.name.split("_", 1)[0] == file_id:
            record = _file_record(path)
            return FileResponse(
                path,
                filename=record["filename"],
                media_type=record["content_type"],
            )
    raise HTTPException(status_code=404, detail="File not found")


@web_router.delete("/files/{file_id}")
async def delete_file(file_id: str) -> dict[str, Any]:
    if not UPLOAD_DIR.exists():
        raise HTTPException(status_code=404, detail="File not found")
    for path in UPLOAD_DIR.iterdir():
        if path.is_file() and path.name.split("_", 1)[0] == file_id:
            path.unlink()
            return {"success": True, "deleted": file_id}
    raise HTTPException(status_code=404, detail="File not found")


@web_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    __: bool = Depends(_validate_api_key),
) -> dict[str, Any]:
    """Store a file and return its extracted text."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())
    safe_name = Path(file.filename or "upload").name
    file_path = UPLOAD_DIR / f"{file_id}_{safe_name}"

    content = await file.read()
    file_path.write_bytes(content)

    extracted_text = _read_extracted(file_path)
    content_type = file.content_type or mimetypes.guess_type(safe_name)[0] or ""

    if not extracted_text:
        if _classify(safe_name, content_type) == "image":
            extracted_text = f"[Image: {safe_name} — no text layer]"
        else:
            extracted_text = f"[{safe_name} — no extractable text]"

    return {
        "file_id": file_id,
        "filename": safe_name,
        "size": len(content),
        "content_type": content_type,
        "kind": _classify(safe_name, content_type),
        "extracted_text": extracted_text[:50000],
    }


# ── Memory ───────────────────────────────────────────────────────────────────


def _iso_or_none(value: Any) -> str | None:
    """Memory timestamps arrive as datetime, float epoch, or string."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    if isinstance(value, int | float):
        from datetime import datetime

        return datetime.fromtimestamp(value, tz=UTC).isoformat()
    return str(value)


@web_router.get("/memory")
async def list_memories(
    session_id: str | None = None, q: str = "", limit: int = 200
) -> dict[str, Any]:
    container = bootstrap_system()
    try:
        records = container.memory_service._manager.get_all()
    except Exception as exc:  # noqa: BLE001
        return {"memories": [], "total": 0, "error": str(exc)}

    out = []
    for m in records:
        value = getattr(m, "value", "") or ""
        key = getattr(m, "memory_type", "") or ""
        if session_id and session_id not in key:
            continue
        if q and q.lower() not in value.lower() and q.lower() not in key.lower():
            continue
        out.append(
            {
                "id": m.id,
                "value": value,
                "key": key,
                # The rule-derived type (university / college / birthday /
                # meeting ...). The domain object names this field
                # ``memory_type`` (loaded from the JSON ``type`` key), and
                # ``key`` is only a fallback for records written before types
                # existed. Exposed because "education" alone cannot distinguish
                # "which university" from "which college".
                "type": getattr(m, "memory_type", None) or key,
                "category": getattr(m, "category", "general"),
                "importance": getattr(m, "importance", None),
                "created_at": _iso_or_none(getattr(m, "created_at", None)),
            }
        )

    out.sort(key=lambda r: str(r["created_at"] or ""), reverse=True)
    return {"memories": out[:limit], "total": len(out)}


@web_router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str) -> dict[str, Any]:
    container = bootstrap_system()
    try:
        return {"success": container.memory_service._manager.delete(memory_id)}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}


# ── Conversations ────────────────────────────────────────────────────────────


@web_router.delete("/conversations/{session_id}")
async def delete_conversation(session_id: str) -> dict[str, Any]:
    """Delete a conversation and wipe every memory tied to it."""
    container = bootstrap_system()
    try:
        deleted = 0
        for mem in container.memory_service._manager.get_all():
            in_session = session_id in (getattr(mem, "memory_type", "") or "")
            if in_session and container.memory_service._manager.delete(mem.id):
                deleted += 1
        return {"success": True, "deleted_memories": deleted}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}


# ── AGY ──────────────────────────────────────────────────────────────────────


@web_router.get("/agy/status")
async def agy_status() -> dict[str, Any]:
    from app.adapters.integrations.agy import is_available

    return {"available": is_available()}


@web_router.get("/agy/models")
async def agy_models() -> dict[str, Any]:
    from app.adapters.integrations.agy import get_models

    return {"models": get_models()}


@web_router.post("/agy/analyze-file")
async def agy_analyze_file(payload: dict[str, Any]) -> dict[str, Any]:
    from app.adapters.integrations.agy import analyze_file

    file_path = payload.get("file_path", "")
    query = payload.get("query", "What is this file about?")
    model = payload.get("model", "gemini-3.1-pro-high")

    if not file_path:
        raise HTTPException(status_code=400, detail="file_path required")

    try:
        return {"response": analyze_file(file_path, query, model=model)}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


# ── Health ───────────────────────────────────────────────────────────────────


@web_router.get("/health")
async def web_health() -> dict[str, Any]:
    return {"status": "ok", "service": "JARVIS Web API"}
