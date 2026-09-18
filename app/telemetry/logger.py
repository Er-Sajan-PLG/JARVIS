"""Telemetry & Event Logger.

Subscribes to InMemoryAsyncBus events for passive telemetry, token cost auditing, and structured logging.
"""

import logging

from app.events import InMemoryAsyncBus, StepExecutionEvent, TelemetryEvent, TokenUsageEvent

logger = logging.getLogger("jarvis.telemetry")

# OTel semantic convention attributes
OTEL_AGENT_NAME = "gen_ai.agent.name"
OTEL_TOOL_NAME = "gen_ai.tool.name"
OTEL_GUARDRAIL_RESULT = "gen_ai.guardrail.result"


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
        logger.info(
            f"[TELEMETRY] [{OTEL_AGENT_NAME}={event.component}] "
            f"[{OTEL_TOOL_NAME}={event.category}] "
            f"duration={event.duration_ms or 0.0}ms metadata={event.data}"
        )

    async def _on_step_execution(self, event: StepExecutionEvent) -> None:
        logger.info(
            f"[STEP] [{OTEL_AGENT_NAME}=jarvis] "
            f"[{OTEL_TOOL_NAME}={event.step_id}] "
            f"plan={event.plan_id} step={event.step_id} title='{event.title}' "
            f"status={event.status.value} error={event.error or 'none'}"
        )

    async def _on_token_usage(self, event: TokenUsageEvent) -> None:
        logger.info(
            f"[COST AUDIT] provider={event.provider} model={event.model} "
            f"tokens={event.total_tokens} (prompt={event.prompt_tokens}, completion={event.completion_tokens}) "
            f"cost=${event.estimated_cost_usd:.6f}"
        )
