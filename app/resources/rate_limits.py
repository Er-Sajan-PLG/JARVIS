"""Provider RPM / TPM Rate Limit Tracker.

Tracks requests per minute (RPM) and tokens per minute (TPM) per provider.
"""

import time
from collections import deque


class RateLimitTracker:
    """Tracks sliding window RPM and TPM for LLM providers."""

    def __init__(self, window_seconds: int = 60) -> None:
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = {}
        self._tokens: dict[str, deque[tuple[float, int]]] = {}

    def record_request(self, provider: str, token_count: int = 0) -> None:
        """Record an API request and token consumption for a provider."""
        now = time.time()
        if provider not in self._requests:
            self._requests[provider] = deque()
            self._tokens[provider] = deque()

        self._requests[provider].append(now)
        if token_count > 0:
            self._tokens[provider].append((now, token_count))

        self._prune(provider, now)

    def get_rpm(self, provider: str) -> int:
        """Get current requests per minute for provider."""
        now = time.time()
        self._prune(provider, now)
        return len(self._requests.get(provider, []))

    def get_tpm(self, provider: str) -> int:
        """Get current tokens per minute for provider."""
        now = time.time()
        self._prune(provider, now)
        return sum(t[1] for t in self._tokens.get(provider, []))

    def _prune(self, provider: str, now: float) -> None:
        """Prune timestamps older than window_seconds."""
        cutoff = now - self.window_seconds
        if provider in self._requests:
            while self._requests[provider] and self._requests[provider][0] < cutoff:
                self._requests[provider].popleft()
        if provider in self._tokens:
            while self._tokens[provider] and self._tokens[provider][0][0] < cutoff:
                self._tokens[provider].popleft()
