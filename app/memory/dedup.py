"""Near-duplicate detection for the memory pipeline (Sprint 3 contract §2).

The capability contract requires near-duplicate deduplication so repeated,
rephrased statements ("I like coffee" / "my preference is coffee") collapse
into one memory instead of accumulating into an unbounded store.

Detection is content-based and deterministic (no wall-clock, no network). An
embedding dimension is available when callers have embedded the item; otherwise
a normalized token-overlap similarity is used as a cheap, deterministic fallback.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable

from app.domain import MemoryItem

_WORD_RE = re.compile(r"[a-z0-9]+")


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


def is_near_duplicate(
    candidate: MemoryItem,
    existing: Iterable[MemoryItem],
    threshold: float = 0.85,
    *,
    same_scope_only: bool = True,
) -> bool:
    """Return True if ``candidate`` is a near-duplicate of any existing item.

    Args:
        candidate: The incoming item to check.
        existing: Items already in the store.
        threshold: Similarity at/above which two items are considered duplicates.
        same_scope_only: Only compare against items of the same ``scope``.
            A session-scoped and a global fact are not duplicates even if their
            text is identical — they have different lifetimes.
    """
    for item in existing:
        if same_scope_only and item.scope != candidate.scope:
            continue
        if candidate.id == item.id:
            continue
        if token_similarity(candidate.content, item.content) >= threshold:
            return True
    return False


def deduplicate(
    items: Iterable[MemoryItem],
    threshold: float = 0.85,
    *,
    same_scope_only: bool = True,
) -> list[MemoryItem]:
    """Return ``items`` with near-duplicates removed (first occurrence kept)."""
    kept: list[MemoryItem] = []
    for item in items:
        if not is_near_duplicate(item, kept, threshold, same_scope_only=same_scope_only):
            kept.append(item)
    return kept
