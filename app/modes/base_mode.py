"""Mode contract (Migration Plan Step 3).

``BaseMode`` is the ABC every operational mode implements. v1 is a facade:
``handle`` passes through and ``format_response`` is identity. Mode-specific
behavior lands in later steps without changing this contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseMode(ABC):
    """Abstract operational mode: identity, prompt, handling, formatting."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Machine-readable mode name (e.g. ``"production"``)."""
        ...

    @property
    @abstractmethod
    def emoji(self) -> str:
        """Display emoji for the mode (e.g. ``"⚡"``)."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt for this mode. Step 3: today's default for all modes."""
        ...

    async def handle(self, *args: Any, **kwargs: Any) -> Any:
        """Handle a request. Step 3: passthrough (first positional arg or None)."""
        if args:
            return args[0]
        return None

    def format_response(self, text: str) -> str:
        """Format a response. Step 3: identity (returns input untouched)."""
        return text
