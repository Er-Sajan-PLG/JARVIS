"""
Live OpenRouter model catalog.

OpenRouter exposes a public (no-auth) endpoint listing *every* model it serves.
We use it so the user can browse and pick any model at runtime without having
to hardcode each one in config.yaml — OpenRouter routes dynamically to whatever
model id we pass as the request ``name``.

The list is cached in-process for a short TTL so repeated menu refreshes
(in the CLI or web UI) don't hammer the endpoint.
"""

from __future__ import annotations

import os
import threading
import time

import requests

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

CATALOG_URL = "https://openrouter.ai/api/v1/models"
_TTL_SECONDS = 300  # 5 minutes

_cache: dict = {"data": None, "fetched_at": 0.0}
_cache_lock = threading.Lock()


def _resolve_key(api_key: str = "") -> str:
    """Fall back to the environment when no key is passed explicitly."""
    if api_key:
        return api_key
    return os.environ.get("OPENROUTER_API_KEY") or ""


def fetch_openrouter_models(force: bool = False, api_key: str = "") -> list[dict]:
    """Return the live OpenRouter model catalog.

    Each entry is ``{"id", "name", "description", "context_length", "pricing"}``.
    Returns an empty list on any failure (network down, keyless is fine — the
    endpoint is public) so callers can fall back to configured presets.
    """
    api_key = _resolve_key(api_key)
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
    except Exception as e:  # pragma: no cover - depends on network
        logger.warning("Failed to fetch OpenRouter catalog: %s", e)
        # Serve stale cache if we have it, else empty list.
        with _cache_lock:
            return _cache["data"] or []


def is_free_model(m: dict) -> bool:
    """True if a catalog entry is free to use (zero prompt + completion cost).

    OpenRouter reports pricing as strings; "0" (or "0.0") means free. Some
    entries omit pricing entirely — treat those as non-free to avoid surprises.
    """
    pricing = m.get("pricing") or {}
    prompt = str(pricing.get("prompt", "")).strip()
    completion = str(pricing.get("completion", "")).strip()
    return prompt in ("0", "0.0") and completion in ("0", "0.0")


def search_openrouter_models(query: str, limit: int = 50, free_only: bool = False) -> list[dict]:
    """Filter the catalog by a free-text query (substring, case-insensitive).

    Used by the web UI search box. Returns up to ``limit`` matches, newest
    (largest context) first for visibility of flagship models.

    When ``free_only`` is True, only models whose ``pricing.prompt`` and
    ``pricing.completion`` are both ``"0"`` are returned — i.e. the models
    OpenRouter serves at no cost (their ids typically end in ``:free``).
    """
    models = fetch_openrouter_models()
    if free_only:
        models = [m for m in models if is_free_model(m)]
    q = (query or "").strip().lower()
    if q:
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    # Stable-ish ordering: longest context first, then by id.
    models = sorted(models, key=lambda m: (m["context_length"], m["id"]), reverse=True)
    return models[:limit]
