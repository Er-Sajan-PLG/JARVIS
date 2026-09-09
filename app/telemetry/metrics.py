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

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        m = self.metrics
        return f'''# HELP jarvis_requests_total Total number of requests
# TYPE jarvis_requests_total counter
jarvis_requests_total {m.total_requests}

# HELP jarvis_tokens_total Total number of tokens processed
# TYPE jarvis_tokens_total counter
jarvis_tokens_total {m.total_tokens}

# HELP jarvis_cost_usd_total Total cost in USD
# TYPE jarvis_cost_usd_total counter
jarvis_cost_usd_total {m.total_cost_usd}

# HELP jarvis_failed_steps_total Total number of failed steps
# TYPE jarvis_failed_steps_total counter
jarvis_failed_steps_total {m.failed_steps}
'''
