"""Live Google AI Studio (Gemini) model catalog.

Reads GOOGLE_API_KEY / GEMINI_API_KEY from the environment when no key is
passed explicitly, so the web layer never has to handle credentials itself.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import requests

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

CATALOG_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_TTL_SECONDS = 300

_cache: dict[str, Any] = {"data": None, "fetched_at": 0.0}
_cache_lock = threading.Lock()


def _resolve_key(api_key: str = "") -> str:
    if api_key:
        return api_key
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""


def fetch_google_models(api_key: str = "", force: bool = False) -> list[dict[str, Any]]:
    """Return the live Gemini catalog (generateContent-capable models only)."""
    key = _resolve_key(api_key)
    if not key:
        return []

    now = time.time()
    with _cache_lock:
        if not force and _cache["data"] is not None and (now - _cache["fetched_at"] < _TTL_SECONDS):
            return list(_cache["data"])

    try:
        resp = requests.get(CATALOG_URL, params={"key": key}, timeout=10)
        resp.raise_for_status()
        raw: list[dict[str, Any]] = resp.json().get("models", [])
        models: list[dict[str, Any]] = []
        for m in raw:
            methods = m.get("supportedGenerationMethods", []) or []
            if "generateContent" not in methods:
                continue
            full = m.get("name", "")
            model_id = full.split("/")[-1] if full else ""
            if not model_id:
                continue
            models.append(
                {
                    "id": model_id,
                    "name": m.get("displayName", model_id),
                    "description": m.get("description", ""),
                    "context_length": m.get("inputTokenLimit", 0) or 0,
                    "pricing": {},
                }
            )
        with _cache_lock:
            _cache["data"] = models
            _cache["fetched_at"] = now
        return models
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch Google catalog: %s", exc)
        with _cache_lock:
            return _cache["data"] or []


def search_google_models(query: str, limit: int = 50, api_key: str = "") -> list[dict[str, Any]]:
    """Filter the Gemini catalog by query."""
    models = fetch_google_models(api_key)
    q = (query or "").strip().lower()
    if q:
        models = [m for m in models if q in m["id"].lower() or q in (m.get("name") or "").lower()]
    return models[:limit]
