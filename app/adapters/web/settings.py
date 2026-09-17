"""Web settings store — single source of truth for the JARVIS web console.

Persists to ``data/web_settings.json`` (gitignored). Holds:

* ``default_provider`` / ``default_model`` — the model new chats start with
* ``custom_providers`` — user-declared OpenAI-compatible endpoints
* ``custom_models``   — manually declared models (discovered or hand-added)
* ``hidden_models``   — models the user disabled
* ``api_keys``        — provider credentials (never returned to the client)

Security: API key *values* are stored server-side and are never serialised
into any HTTP response. Only ``has_key`` booleans cross the wire.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_STORAGE_PATH = _PROJECT_ROOT / "data" / "web_settings.json"
_lock = threading.Lock()

_DEFAULTS: dict[str, Any] = {
    "default_provider": "",
    "default_model": "",
    "custom_providers": [],
    "custom_models": [],
    "hidden_models": [],
    "api_keys": {},
}

MASK = "••••••••"


def _load() -> dict[str, Any]:
    """Load settings, filling in any keys missing from an older file.

    Returns freshly-constructed containers every call. A shallow ``dict()``
    copy would share the mutable lists/dicts held in ``_DEFAULTS``, so callers
    appending to the result would corrupt the module defaults.
    """
    data: dict[str, Any] = {
        "default_provider": "",
        "default_model": "",
        "custom_providers": [],
        "custom_models": [],
        "hidden_models": [],
        "api_keys": {},
    }
    try:
        if _STORAGE_PATH.exists():
            stored = json.loads(_STORAGE_PATH.read_text())
            if isinstance(stored, dict):
                for key, value in stored.items():
                    if key in data and isinstance(data[key], list) and isinstance(value, list):
                        data[key] = list(value)
                    elif key in data and isinstance(data[key], dict) and isinstance(value, dict):
                        data[key] = dict(value)
                    else:
                        data[key] = value
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load web settings: %s", exc)
    # Defensive: normalise list/dict fields so callers can always iterate.
    for field, empty in (
        ("custom_providers", list),
        ("custom_models", list),
        ("hidden_models", list),
        ("api_keys", dict),
    ):
        if not isinstance(data.get(field), empty):
            data[field] = empty()
    return data


def _save(data: dict[str, Any]) -> None:
    with _lock:
        try:
            _STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = _STORAGE_PATH.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2))
            tmp.replace(_STORAGE_PATH)
            os.chmod(_STORAGE_PATH, 0o600)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to save web settings: %s", exc)
    # Every write can change the merged provider/model catalogue (custom
    # providers, hand-added models, hidden models), so drop the cache. The
    # import is local to avoid a circular import at module load.
    try:
        from app.utils.provider_catalog import invalidate_catalogue_cache

        invalidate_catalogue_cache()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Catalogue cache invalidation skipped: %s", exc)


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")


# ── Default model ────────────────────────────────────────────────────────────


def get_default() -> dict[str, str]:
    data = _load()
    return {
        "provider": data.get("default_provider", ""),
        "model": data.get("default_model", ""),
    }


def set_default(provider: str, model: str) -> dict[str, str]:
    data = _load()
    data["default_provider"] = provider
    data["default_model"] = model
    _save(data)
    return {"provider": provider, "model": model}


# ── Custom providers ─────────────────────────────────────────────────────────


def get_custom_providers() -> list[dict[str, Any]]:
    """Return custom providers with keys redacted."""
    out = []
    for p in _load()["custom_providers"]:
        safe = {k: v for k, v in p.items() if k != "api_key"}
        safe["has_key"] = bool(p.get("api_key"))
        out.append(safe)
    return out


def get_custom_providers_with_keys() -> list[dict[str, Any]]:
    """Internal use only — includes credentials for outbound calls."""
    return list(_load()["custom_providers"])


def add_custom_provider(provider: dict[str, Any]) -> dict[str, Any]:
    """Add or replace a custom provider. Returns the redacted record."""
    data = _load()
    providers = data["custom_providers"]
    key = _slug(provider.get("key") or provider.get("name") or "")
    if not key:
        raise ValueError("provider name is required")

    record = {
        "key": key,
        "name": provider.get("name") or key,
        "base_url": (provider.get("base_url") or "").rstrip("/"),
        "api_key": provider.get("api_key") or "",
        "models": provider.get("models") or [],
        # Provider-level defaults applied to models that don't declare their own.
        "context_length": int(provider.get("context_length") or 0),
        "capabilities": list(provider.get("capabilities") or []),
        "is_custom": True,
    }

    for i, existing in enumerate(providers):
        if existing.get("key") == key:
            # Keep the old key when the caller sent a masked placeholder.
            if record["api_key"] in ("", MASK):
                record["api_key"] = existing.get("api_key", "")
            if not record["models"]:
                record["models"] = existing.get("models", [])
            # Preserve provider defaults the caller didn't restate.
            if not record["context_length"]:
                record["context_length"] = int(existing.get("context_length") or 0)
            if not record["capabilities"]:
                record["capabilities"] = list(existing.get("capabilities") or [])
            providers[i] = record
            break
    else:
        providers.append(record)

    data["custom_providers"] = providers
    _save(data)
    safe = {k: v for k, v in record.items() if k != "api_key"}
    safe["has_key"] = bool(record["api_key"])
    return safe


def delete_custom_provider(key: str) -> bool:
    data = _load()
    providers = data["custom_providers"]
    remaining = [p for p in providers if p.get("key") != key]
    if len(remaining) == len(providers):
        return False
    data["custom_providers"] = remaining
    # Cascade: drop that provider's custom models too.
    data["custom_models"] = [m for m in data["custom_models"] if m.get("provider") != key]
    _save(data)
    return True


# ── Custom models ────────────────────────────────────────────────────────────


def get_custom_models() -> list[dict[str, Any]]:
    return list(_load()["custom_models"])


def add_custom_model(model: dict[str, Any]) -> dict[str, Any]:
    """Register a single model against a provider (common or custom)."""
    data = _load()
    provider = (model.get("provider") or "").strip()
    model_id = (model.get("id") or "").strip()
    if not provider or not model_id:
        raise ValueError("provider and id are required")

    record = {
        "provider": provider,
        "id": model_id,
        "name": model.get("name") or model_id,
        "description": model.get("description", ""),
        "context_length": model.get("context_length") or 0,
        "pricing": model.get("pricing") or {},
        "capabilities": model.get("capabilities") or [],
        "is_custom": True,
    }

    models = data["custom_models"]
    for i, existing in enumerate(models):
        if existing.get("provider") == provider and existing.get("id") == model_id:
            models[i] = record
            break
    else:
        models.append(record)

    data["custom_models"] = models
    _save(data)
    return record


def delete_custom_model(provider: str, model_id: str) -> bool:
    data = _load()
    models = data["custom_models"]
    remaining = [
        m for m in models if not (m.get("provider") == provider and m.get("id") == model_id)
    ]
    if len(remaining) == len(models):
        return False
    data["custom_models"] = remaining
    _save(data)
    return True


# ── Hidden models ────────────────────────────────────────────────────────────


def get_hidden_models() -> list[str]:
    return list(_load()["hidden_models"])


def toggle_hidden_model(provider: str, model_id: str) -> bool:
    """Hide/show a model. Returns the new hidden state."""
    data = _load()
    token = f"{provider}:{model_id}"
    hidden = data["hidden_models"]
    if token in hidden:
        hidden.remove(token)
        state = False
    else:
        hidden.append(token)
        state = True
    data["hidden_models"] = hidden
    _save(data)
    return state


# ── API keys ─────────────────────────────────────────────────────────────────


def get_api_keys() -> dict[str, str]:
    """Internal use only — raw credential values."""
    return dict(_load()["api_keys"])


def get_api_key_status() -> dict[str, bool]:
    """Redacted view for the UI: which providers have a key configured."""
    return {k: bool(v) for k, v in _load()["api_keys"].items()}


def set_api_key(provider: str, value: str) -> None:
    data = _load()
    keys = data["api_keys"]
    if value in ("", MASK):
        return
    keys[provider] = value
    data["api_keys"] = keys
    _save(data)


def delete_api_key(provider: str) -> bool:
    data = _load()
    keys = data["api_keys"]
    if provider not in keys:
        return False
    del keys[provider]
    data["api_keys"] = keys
    _save(data)
    return True


def resolve_api_key(provider: str) -> str:
    """Credential for outbound calls: stored value first, then environment."""
    stored = get_api_keys().get(provider)
    if stored:
        return stored
    env_map = {
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
    return os.environ.get(env_map.get(provider, ""), "")
