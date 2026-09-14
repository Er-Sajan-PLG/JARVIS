"""Token-aware context-window management (Sprint 3 contract §6).

Trims a conversation to fit a token budget with a deterministic priority
order: **pinned** messages are always kept, then the **most recent** messages
are kept until the budget is exhausted. This matches the contract's
``recent > pinned > summary`` intent: pinned content is sacred, recency wins
for the rest, and anything left over is dropped (an optional summary slot is
reserved to a caller who has already produced one).

Token counting is approximate (a configurable characters-per-token heuristic)
so this stays pure and deterministic — no external tokenizer dependency in the
domain/context layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain import ConversationState, Message


@dataclass
class TrimResult:
    """The outcome of a trim: the kept messages and what happened to the rest."""

    kept: list[Message]
    dropped: list[Message]
    total_tokens: int
    dropped_tokens: int


DEFAULT_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str, chars_per_token: int = DEFAULT_CHARS_PER_TOKEN) -> int:
    """Approximate token count from a string using a character heuristic."""
    if not text:
        return 0
    return max(1, (len(text) + chars_per_token - 1) // chars_per_token)


def trim_conversation(
    conversation: ConversationState,
    max_tokens: int,
    *,
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
    pinned_always_kept: bool = True,
    summary: str = "",
) -> TrimResult:
    """Trim ``conversation`` to fit ``max_tokens``.

    Priority (highest first):
      1. Explicit summary (if provided), counted first as its own slot.
      2. Pinned messages (always kept when ``pinned_always_kept``).
      3. Most-recent messages, newest first.

    Args:
        conversation: The conversation to trim (not mutated).
        max_tokens: The hard token budget.
        chars_per_token: Heuristic for token estimation.
        pinned_always_kept: If True, pinned messages are never dropped even if
            they alone would exceed the budget.
        summary: Optional precomputed summary text to reserve space for.

    Returns:
        A ``TrimResult`` describing kept/dropped messages and token usage.
    """
    messages = conversation.messages

    summary_tokens = estimate_tokens(summary, chars_per_token) if summary else 0

    pinned = [m for m in messages if m.pinned] if pinned_always_kept else []
    pinned_tokens = sum(estimate_tokens(m.content, chars_per_token) for m in pinned)

    unpinned = [m for m in messages if not m.pinned]
    # Newest first for the recency priority.
    remaining_budget = max(0, max_tokens - summary_tokens - pinned_tokens)

    kept_recent: list[Message] = []
    used = 0
    for m in reversed(unpinned):
        cost = estimate_tokens(m.content, chars_per_token)
        if used + cost <= remaining_budget:
            kept_recent.append(m)
            used += cost

    # Restore chronological order for the kept slice.
    kept_recent.reverse()

    kept = pinned + kept_recent
    # Chronological order overall: pinned interleaving is approximate but stable.
    kept.sort(key=lambda m: messages.index(m) if m in messages else 0)

    kept_ids = {id(m) for m in kept}
    dropped = [m for m in messages if id(m) not in kept_ids]

    total_tokens = summary_tokens + pinned_tokens + used
    dropped_tokens = sum(estimate_tokens(m.content, chars_per_token) for m in dropped)

    return TrimResult(
        kept=kept,
        dropped=dropped,
        total_tokens=total_tokens,
        dropped_tokens=dropped_tokens,
    )
