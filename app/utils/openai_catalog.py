"""
Live OpenAI model catalog.

OpenAI doesn't have a public models endpoint, so we maintain a curated list
with known models and their metadata. This can be updated as OpenAI releases new models.
"""

from __future__ import annotations

import threading
import time

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

# Curated list of known OpenAI models (updated periodically)
# Pricing is in USD per 1M tokens
_KNOWN_MODELS = [
    {
        "id": "gpt-4o",
        "name": "GPT-4o",
        "description": "OpenAI's most advanced multimodal model",
        "context_length": 128000,
        "pricing": {"prompt": "2.50", "completion": "10.00"},
    },
    {
        "id": "gpt-4o-mini",
        "name": "GPT-4o Mini",
        "description": "Fast, affordable small model",
        "context_length": 128000,
        "pricing": {"prompt": "0.15", "completion": "0.60"},
    },
    {
        "id": "gpt-4-turbo",
        "name": "GPT-4 Turbo",
        "description": "Previous generation GPT-4 with 128k context",
        "context_length": 128000,
        "pricing": {"prompt": "10.00", "completion": "30.00"},
    },
    {
        "id": "gpt-4",
        "name": "GPT-4",
        "description": "Original GPT-4 model",
        "context_length": 8192,
        "pricing": {"prompt": "30.00", "completion": "60.00"},
    },
    {
        "id": "gpt-3.5-turbo",
        "name": "GPT-3.5 Turbo",
        "description": "Fast, cost-effective model for everyday tasks",
        "context_length": 16384,
        "pricing": {"prompt": "0.50", "completion": "1.50"},
    },
    {
        "id": "o1-preview",
        "name": "o1 Preview",
        "description": "Reasoning model with advanced chain-of-thought",
        "context_length": 128000,
        "pricing": {"prompt": "15.00", "completion": "60.00"},
    },
    {
        "id": "o1-mini",
        "name": "o1 Mini",
        "description": "Faster, cheaper reasoning model",
        "context_length": 128000,
        "pricing": {"prompt": "3.00", "completion": "12.00"},
    },
]

_TTL_SECONDS = 86400  # 24 hours (curated list, rarely changes)

_cache: dict = {"data": None, "fetched_at": 0.0}
_cache_lock = threading.Lock()


def fetch_openai_models(force: bool = False) -> list[dict]:
    """Return the curated OpenAI model catalog."""
    now = time.time()
    with _cache_lock:
        if not force and _cache["data"] is not None and (now - _cache["fetched_at"] < _TTL_SECONDS):
            return _cache["data"]

    with _cache_lock:
        _cache["data"] = _KNOWN_MODELS.copy()
        _cache["fetched_at"] = now
    return _KNOWN_MODELS


def is_free_model(m: dict) -> bool:
    """OpenAI models are never free."""
    return False


def search_openai_models(query: str, limit: int = 50, free_only: bool = False) -> list[dict]:
    """Filter the catalog by a free-text query."""
    if free_only:
        return []
    models = fetch_openai_models()
    q = (query or "").strip().lower()
    if q:
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    models = sorted(models, key=lambda m: (m["context_length"], m["id"]), reverse=True)
    return models[:limit]
