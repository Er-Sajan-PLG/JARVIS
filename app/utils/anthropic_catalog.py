"""
Live Anthropic (Claude) model catalog.

Anthropic doesn't have a public models endpoint, so we maintain a curated list
with known models and their metadata.
"""

from __future__ import annotations

import threading
import time

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

# Curated list of known Anthropic models
# Pricing is in USD per 1M tokens
_KNOWN_MODELS = [
    {
        "id": "claude-3-5-sonnet-20241022",
        "name": "Claude 3.5 Sonnet (New)",
        "description": "Anthropic's most intelligent model (Oct 2024)",
        "context_length": 200000,
        "pricing": {"prompt": "3.00", "completion": "15.00"},
    },
    {
        "id": "claude-3-5-haiku-20241022",
        "name": "Claude 3.5 Haiku",
        "description": "Fast, affordable model for everyday tasks",
        "context_length": 200000,
        "pricing": {"prompt": "0.80", "completion": "4.00"},
    },
    {
        "id": "claude-3-opus-20240229",
        "name": "Claude 3 Opus",
        "description": "Anthropic's most capable model for complex tasks",
        "context_length": 200000,
        "pricing": {"prompt": "15.00", "completion": "75.00"},
    },
    {
        "id": "claude-3-sonnet-20240229",
        "name": "Claude 3 Sonnet",
        "description": "Balanced performance and speed",
        "context_length": 200000,
        "pricing": {"prompt": "3.00", "completion": "15.00"},
    },
    {
        "id": "claude-3-haiku-20240307",
        "name": "Claude 3 Haiku",
        "description": "Fastest and most compact model",
        "context_length": 200000,
        "pricing": {"prompt": "0.25", "completion": "1.25"},
    },
]

_TTL_SECONDS = 86400  # 24 hours

_cache: dict = {"data": None, "fetched_at": 0.0}
_cache_lock = threading.Lock()


def fetch_anthropic_models(force: bool = False) -> list[dict]:
    """Return the curated Anthropic model catalog."""
    now = time.time()
    with _cache_lock:
        if not force and _cache["data"] is not None and (now - _cache["fetched_at"] < _TTL_SECONDS):
            return _cache["data"]

    with _cache_lock:
        _cache["data"] = _KNOWN_MODELS.copy()
        _cache["fetched_at"] = now
    return _KNOWN_MODELS


def is_free_model(m: dict) -> bool:
    """Anthropic models are never free."""
    return False


def search_anthropic_models(query: str, limit: int = 50, free_only: bool = False) -> list[dict]:
    """Filter the catalog by a free-text query."""
    if free_only:
        return []
    models = fetch_anthropic_models()
    q = (query or "").strip().lower()
    if q:
        models = [m for m in models if q in m["id"].lower() or q in m["name"].lower()]
    models = sorted(models, key=lambda m: (m["context_length"], m["id"]), reverse=True)
    return models[:limit]
