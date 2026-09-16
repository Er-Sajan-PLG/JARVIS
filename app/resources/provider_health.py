"""Provider Health & Circuit Breaker Tracking.

Monitors provider availability, tracks 429 / 503 error rates, and implements circuit breaking.
"""

import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker state."""

    CLOSED = "closed"  # Healthy, accepting traffic
    OPEN = "open"  # Failing / rate-limited, rejecting traffic
    HALF_OPEN = "half_open"  # Probing recovery


class ProviderHealthMonitor:
    """Monitors provider health and manages circuit breaker status."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_time_seconds: float = 30.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_time_seconds = recovery_time_seconds
        self._states: dict[str, CircuitState] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._last_failure_time: dict[str, float] = {}

    def is_available(self, provider: str) -> bool:
        """Check if circuit is closed (or recovered from open)."""
        state = self._states.get(provider, CircuitState.CLOSED)
        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            last_failed = self._last_failure_time.get(provider, 0.0)
            if time.time() - last_failed >= self.recovery_time_seconds:
                logger.info("Circuit breaker for '%s' moving from OPEN to HALF_OPEN", provider)
                self._states[provider] = CircuitState.HALF_OPEN
                return True
            return False

        return True  # HALF_OPEN allows probe request

    def record_success(self, provider: str) -> None:
        """Record successful call, resetting circuit to CLOSED."""
        self._consecutive_failures[provider] = 0
        if self._states.get(provider) != CircuitState.CLOSED:
            logger.info("Provider '%s' recovered to healthy CLOSED state", provider)
            self._states[provider] = CircuitState.CLOSED

    def record_failure(self, provider: str, error_code: int | None = None) -> None:
        """Record provider failure (429 rate limit, 503 service unavailable, timeout)."""
        now = time.time()
        self._last_failure_time[provider] = now
        failures = self._consecutive_failures.get(provider, 0) + 1
        self._consecutive_failures[provider] = failures

        if failures >= self.failure_threshold or error_code in (429, 503):
            logger.warning(
                "Circuit breaker OPENED for provider '%s' (Failures: %d, Error: %s)",
                provider,
                failures,
                error_code,
            )
            self._states[provider] = CircuitState.OPEN
