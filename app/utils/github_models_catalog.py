"""Live GitHub Models catalog."""

from __future__ import annotations

import threading
import time

import requests

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

# GitHub models list from their docs
MODELS_LIST = [
    {"id": "gpt-4o", "name": "GPT-4o"},
    {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"},
    {"id": "phi-3.5-mini-instruct", "name": "Phi-3.5 Mini"},
    {"id": "phi-3-medium-instruct", "name": "Phi-3 Medium"},
    {"id": "phi-3-small-instruct", "name": "Phi-3 Small"},
    {"id": "llama-3.1-405b-instruct", "name": "Llama 3.1 405B"},
    {"id": "llama-3.1-70b-instruct", "name": "Llama 3.1 70B"},
    {"id": "mistral-large", "name": "Mistral Large"},
    {"id": "mistral-nemo", "name": "Mistral Nemo"},
]

_cache: dict = {"data": None, "fetched_at": 0.0}
_cache_lock = threading.Lock()


def fetch_github_models(force: bool = False) -> list[dict]:
    """Return available GitHub Models."""
    now = time.time()
    with _cache_lock:
        if not force and _cache["data"] is not None and (
            now - _cache["fetched_at"] < 3600
        ):
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


def search_github_models(query: str, limit: int = 50) -> list[dict]:
    """Filter GitHub models by query."""
    models = fetch_github_models()
    q = (query or "").strip().lower()
    if q:
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    return models[:limit]
