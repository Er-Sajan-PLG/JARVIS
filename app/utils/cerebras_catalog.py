"""
Live Cerebras model catalog.

Cerebras exposes a public endpoint listing available models.
We cache it in-process with a TTL.
"""

from __future__ import annotations

import threading
import time

import requests

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

CATALOG_URL = "https://api.cerebras.ai/v1/models"
_TTL_SECONDS = 3600  # 1 hour

_cache: dict = {"data": None, "fetched_at": 0.0}
_cache_lock = threading.Lock()


def fetch_cerebras_models(force: bool = False) -> list[dict]:
    """Return the live Cerebras model catalog.

    Each entry is {"id", "name", "description", "context_length", "pricing"}.
    Returns an empty list on any failure.
    """
    now = time.time()
    with _cache_lock:
        if not force and _cache["data"] is not None and (now - _cache["fetched_at"] < _TTL_SECONDS):
            return _cache["data"]

    try:
        resp = requests.get(CATALOG_URL, timeout=10)
        resp.raise_for_status()
        raw = resp.json().get("data", [])
        models = [
            {
                "id": m.get("id", ""),
                "name": m.get("name") or m.get("id", ""),
                "description": (m.get("description") or "").strip(),
                "context_length": m.get("context_length") or 0,
                "pricing": m.get("pricing") or {},
            }
            for m in raw
            if m.get("id")
        ]
        with _cache_lock:
            _cache["data"] = models
            _cache["fetched_at"] = now
        return models
    except Exception as e:
        logger.warning("Failed to fetch Cerebras catalog: %s", e)
        with _cache_lock:
            return _cache["data"] or []


def is_free_model(m: dict) -> bool:
    """True if a catalog entry is free."""
    pricing = m.get("pricing") or {}
    prompt = str(pricing.get("prompt", "")).strip()
    completion = str(pricing.get("completion", "")).strip()
    return prompt in ("0", "0.0") and completion in ("0", "0.0")


def search_cerebras_models(query: str, limit: int = 50, free_only: bool = False) -> list[dict]:
    """Filter the catalog by a free-text query."""
    models = fetch_cerebras_models()
    if free_only:
        models = [m for m in models if is_free_model(m)]
    q = (query or "").strip().lower()
    if q:
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    models = sorted(models, key=lambda m: (m["context_length"], m["id"]), reverse=True)
    return models[:limit]
