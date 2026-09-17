"""Live Cloudflare Workers AI model catalog."""

from __future__ import annotations

import os
import threading
import time

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

# Static list of Cloudflare Workers AI models
MODELS_LIST = [
    {"id": "@cf/meta/llama-2-7b-chat-int8", "name": "Llama 2 7B Chat"},
    {"id": "@cf/mistral/mistral-7b-instruct-v0.1", "name": "Mistral 7B"},
    {"id": "@cf/thebloke/neural-chat-7b-v3-1-awq", "name": "Neural Chat 7B"},
    {"id": "@cf/openchat/openchat-3.5-0106", "name": "OpenChat 3.5"},
    {"id": "@cf/qwen/qwen-1.8b-chat", "name": "Qwen 1.8B Chat"},
    {"id": "@cf/baai/bge-small-en-v1.5", "name": "BGE Small EN"},
]

_cache: dict = {"data": None, "fetched_at": 0.0}
_cache_lock = threading.Lock()


def _resolve_key(api_key: str = "") -> str:
    """Fall back to the environment when no key is passed explicitly."""
    if api_key:
        return api_key
    return os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CLOUDFLARE_API_KEY") or ""


def fetch_cloudflare_models(force: bool = False, api_key: str = "") -> list[dict]:
    """Return available Cloudflare Workers AI models."""
    api_key = _resolve_key(api_key)
    now = time.time()
    with _cache_lock:
        if not force and _cache["data"] is not None and (now - _cache["fetched_at"] < 3600):
            return _cache["data"]

    models = [
        {
            "id": m["id"],
            "name": m["name"],
            "description": "",
            "context_length": 0,
            "pricing": {},
        }
        for m in MODELS_LIST
    ]

    with _cache_lock:
        _cache["data"] = models
        _cache["fetched_at"] = now

    return models


def search_cloudflare_models(query: str, limit: int = 50) -> list[dict]:
    """Filter Cloudflare models by query."""
    models = fetch_cloudflare_models()
    q = (query or "").strip().lower()
    if q:
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    return models[:limit]
