"""Central Resource Manager Façade.

Combines TokenBudgetManager, RateLimitTracker, and ProviderHealthMonitor into a unified interface.
"""

from app.resources.budget import TokenBudgetManager
from app.resources.provider_health import ProviderHealthMonitor
from app.resources.rate_limits import RateLimitTracker


class ResourceManager:
    """Central manager for LLM tokens, costs, rate limits, and health monitoring."""

    def __init__(self) -> None:
        self.budget = TokenBudgetManager()
        self.rate_limits = RateLimitTracker()
        self.health = ProviderHealthMonitor()
