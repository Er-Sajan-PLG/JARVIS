"""Near-duplicate detection for the memory pipeline (Sprint 3 contract §2).

The capability contract requires near-duplicate deduplication so repeated,
rephrased statements ("I like coffee" / "my preference is coffee") collapse
into one memory instead of accumulating into an unbounded store.

Detection is content-based and deterministic (no wall-clock, no network).
When both items have embeddings, cosine similarity is used; otherwise a
normalized token-overlap similarity is used as a cheap, deterministic fallback.
"""

from __future__ import annotations

import difflib
import logging
import math
import re
from collections.abc import Iterable
from typing import Any

from app.domain import MemoryItem

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9]+")

# ── Embedding cache (module-level, lazy-loaded) ──────────────────────────

_model: Any = None
_embedding_cache: dict[str, list[float]] = {}


def _get_model() -> Any:
    """Lazily load the sentence-transformers model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.debug("Loaded sentence-transformers model: all-MiniLM-L6-v2")
        except Exception as e:  # noqa: BLE001
            logger.warning("sentence-transformers not available: %s", e)
            _model = None
    return _model


def _get_embedding(text: str) -> list[float] | None:
    """Return the embedding for ``text``, using cache when possible."""
    if not text:
        return None
    if text in _embedding_cache:
        return _embedding_cache[text]
    model = _get_model()
    if model is None:
        return None
    try:
        embedding = model.encode(text).tolist()
        _embedding_cache[text] = embedding
        return embedding
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to compute embedding for %r: %s", text[:50], e)
        return None


def embedding_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two embedding vectors, in [0, 1]."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Token-overlap similarity (fallback) ───────────────────────────────────


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation/noise so rephrasing matches better."""
    return " ".join(_WORD_RE.findall(text.lower()))


def token_similarity(a: str, b: str) -> float:
    """Normalized token-overlap similarity in [0, 1], deterministic."""
    na = _normalize(a)
    nb = _normalize(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


# ── Near-duplicate detection ──────────────────────────────────────────────


def is_near_duplicate(
    candidate: MemoryItem,
    existing: Iterable[MemoryItem],
    threshold: float = 0.85,
    *,
    same_scope_only: bool = True,
    embedding_threshold: float = 0.9,
) -> bool:
    """Return True if ``candidate`` is a near-duplicate of any existing item.

    Uses embedding cosine similarity when both items have embeddings;
    otherwise falls back to token-overlap similarity.

    Args:
        candidate: The incoming item to check.
        existing: Items already in the store.
        threshold: Token-overlap similarity threshold (fallback).
        same_scope_only: Only compare against items of the same ``scope``.
        embedding_threshold: Cosine similarity threshold for embeddings.
    """
    for item in existing:
        if same_scope_only and item.scope != candidate.scope:
            continue
        if candidate.id == item.id:
            continue

        # Try embedding similarity first
        if candidate.embedding is not None and item.embedding is not None:
            sim = embedding_similarity(candidate.embedding, item.embedding)
            if sim >= embedding_threshold:
                return True
            continue  # embeddings present but not similar — don't fall back

        # Fall back to token-overlap
        if token_similarity(candidate.content, item.content) >= threshold:
            return True
    return False


def deduplicate(
    items: Iterable[MemoryItem],
    threshold: float = 0.85,
    *,
    same_scope_only: bool = True,
    embedding_threshold: float = 0.9,
) -> list[MemoryItem]:
    """Return ``items`` with near-duplicates removed (first occurrence kept)."""
    kept: list[MemoryItem] = []
    for item in items:
        if not is_near_duplicate(
            item,
            kept,
            threshold,
            same_scope_only=same_scope_only,
            embedding_threshold=embedding_threshold,
        ):
            kept.append(item)
    return kept
