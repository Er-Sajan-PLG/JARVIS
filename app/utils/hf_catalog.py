"""Live Hugging Face model catalog."""

from __future__ import annotations

import threading
import time

import requests

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

API_URL = "https://huggingface.co/api/models"
_TTL_SECONDS = 300

_cache: dict = {"data": None, "fetched_at": 0.0}
_cache_lock = threading.Lock()


def fetch_hf_models(api_key: str = "", force: bool = False) -> list[dict]:
    """Return the live Hugging Face model catalog."""
    now = time.time()
    with _cache_lock:
        if not force and _cache["data"] is not None and (
            now - _cache["fetched_at"] < _TTL_SECONDS
        ):
            return _cache["data"]

    try:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        resp = requests.get(f"{API_URL}?filter=text-generation", headers=headers, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        models = [
            {
                "id": m.get("id", ""),
                "name": m.get("id", "").split("/")[-1] if "/" in m.get("id", "") else m.get("id", ""),
                "description": "",
                "context_length": 0,
                "pricing": {},
            }
            for m in raw
            if m.get("id")
        ]
        with _cache_lock:
            _cache["data"] = models[:50]  # Limit to first 50
            _cache["fetched_at"] = now
        return _cache["data"]
    except Exception as e:
        logger.warning("Failed to fetch Hugging Face catalog: %s", e)
        with _cache_lock:
            return _cache["data"] or []


def search_hf_models(query: str, limit: int = 50, api_key: str = "") -> list[dict]:
    """Filter Hugging Face catalog by query."""
    models = fetch_hf_models(api_key)
    q = (query or "").strip().lower()
    if q:
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    return models[:limit]
