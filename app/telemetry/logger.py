"""Telemetry & Event Logger.

Subscribes to InMemoryAsyncBus events for passive telemetry, token cost auditing, and structured logging.
"""

import logging
from typing import Any

from app.events import Event, InMemoryAsyncBus, StepExecutionEvent, TelemetryEvent, TokenUsageEvent

logger = logging.getLogger("jarvis.telemetry")


class EventLogger:
    """Subscriber logging passive bus events to standard telemetry output."""

    def __init__(self, bus: InMemoryAsyncBus | None = None) -> None:
        self.bus = bus
        if self.bus:
            self.attach_to_bus(self.bus)

    def attach_to_bus(self, bus: InMemoryAsyncBus) -> None:
        """Register telemetry handlers on the event bus."""
        self.bus = bus
        bus.subscribe("telemetry", self._on_telemetry)
        bus.subscribe("step_execution", self._on_step_execution)
        bus.subscribe("token_usage", self._on_token_usage)
        logger.info("EventLogger attached to InMemoryAsyncBus")

    async def _on_telemetry(self, event: TelemetryEvent) -> None:
        logger.info("[TELEMETRY] [%s:%s] duration=%.2fms metadata=%s", event.component, event.category, event.duration_ms or 0.0, event.data)

    async def _on_step_execution(self, event: StepExecutionEvent) -> None:
        logger.info("[STEP] plan=%s step=%s title='%s' status=%s error=%s", event.plan_id, event.step_id, event.title, event.status.value, event.error or "none")

    async def _on_token_usage(self, event: TokenUsageEvent) -> None:
        logger.info("[COST AUDIT] provider=%s model=%s tokens=%d (prompt=%d, completion=%d) cost=$%.6f", event.provider, event.model, event.total_tokens, event.prompt_tokens, event.completion_tokens, event.estimated_cost_usd)
