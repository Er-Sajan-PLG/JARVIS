"""Token Budget Manager & Cost Tracking.

Tracks session and global token usage across prompt/completion tokens.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Container for token usage metrics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class TokenBudgetManager:
    """Manages token consumption budgets and cost allocation."""

    def __init__(self, max_session_tokens: int = 128000) -> None:
        self.max_session_tokens = max_session_tokens
        self._session_usage: dict[str, TokenUsage] = {}

    def record_usage(
        self,
        session_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float = 0.0,
    ) -> TokenUsage:
        """Record token usage for a session."""
        if session_id not in self._session_usage:
            self._session_usage[session_id] = TokenUsage()

        u = self._session_usage[session_id]
        u.prompt_tokens += prompt_tokens
        u.completion_tokens += completion_tokens
        u.total_tokens += prompt_tokens + completion_tokens
        u.estimated_cost_usd += cost_usd

        logger.debug("Recorded usage for session %s: %d total tokens", session_id, u.total_tokens)
        return u

    def get_session_usage(self, session_id: str) -> TokenUsage:
        """Get accumulated token usage for a session."""
        return self._session_usage.get(session_id, TokenUsage())

    def is_within_budget(self, session_id: str, estimated_tokens: int = 1000) -> bool:
        """Check if session is within maximum token limit."""
        usage = self.get_session_usage(session_id)
        return (usage.total_tokens + estimated_tokens) <= self.max_session_tokens
