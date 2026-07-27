"""Metrics Collector & Aggregator.

Collects passive metrics on token usage, request latencies, and component execution counts.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AggregatedMetrics:
    """Aggregated metrics totals."""
    total_requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    failed_steps: int = 0


class MetricsCollector:
    """Collects and aggregates passive metrics from event bus."""

    def __init__(self) -> None:
        self.metrics = AggregatedMetrics()

    def record_request(self, tokens: int = 0, cost_usd: float = 0.0) -> None:
        """Increment request and token totals."""
        self.metrics.total_requests += 1
        self.metrics.total_tokens += tokens
        self.metrics.total_cost_usd += cost_usd

    def record_step_failure(self) -> None:
        """Increment step failure counter."""
        self.metrics.failed_steps += 1
