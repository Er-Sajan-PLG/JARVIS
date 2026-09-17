"""Live NVIDIA NIM model catalog."""

from __future__ import annotations

import os
import threading
import time

import requests

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

CATALOG_URL = "https://integrate.api.nvidia.com/v1/models"
_TTL_SECONDS = 300

_cache: dict = {"data": None, "fetched_at": 0.0}
_cache_lock = threading.Lock()


def _resolve_key(api_key: str = "") -> str:
    """Fall back to the environment when no key is passed explicitly."""
    if api_key:
        return api_key
    return os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVIDIA_NIM_API_KEY") or ""


def fetch_nvidia_models(api_key: str = "", force: bool = False) -> list[dict]:
    """Return the live NVIDIA NIM model catalog."""
    api_key = _resolve_key(api_key)
    now = time.time()
    with _cache_lock:
        if not force and _cache["data"] is not None and (now - _cache["fetched_at"] < _TTL_SECONDS):
            return _cache["data"]

    try:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        resp = requests.get(CATALOG_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        raw = resp.json().get("data", [])
        models = [
            {
                "id": m.get("id", ""),
                "name": m.get("id", ""),
                "description": m.get("description", ""),
                "context_length": 0,
                "pricing": {},
            }
            for m in raw
            if m.get("id")
        ]
        with _cache_lock:
            _cache["data"] = models
            _cache["fetched_at"] = now
        return models
    except Exception as e:
        logger.warning("Failed to fetch NVIDIA NIM catalog: %s", e)
        with _cache_lock:
            return _cache["data"] or []


def search_nvidia_models(query: str, limit: int = 50, api_key: str = "") -> list[dict]:
    """Filter NVIDIA NIM catalog by query."""
    models = fetch_nvidia_models(api_key)
    q = (query or "").strip().lower()
    if q:
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    return models[:limit]
