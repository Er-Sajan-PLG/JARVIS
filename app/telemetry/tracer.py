"""Operation Latency & Context Tracer.

Measures execution duration for cognitive engine components and publishes TelemetryEvents.
"""

from contextlib import asynccontextmanager
import time
from typing import Any, AsyncGenerator

from app.events import InMemoryAsyncBus, TelemetryEvent

# OTel semantic convention attributes
OTEL_AGENT_NAME = "gen_ai.agent.name"
OTEL_TOOL_NAME = "gen_ai.tool.name"
OTEL_GUARDRAIL_RESULT = "gen_ai.guardrail.result"


class Tracer:
    """Measures execution duration and publishes TelemetryEvents over InMemoryAsyncBus."""

    def __init__(self, bus: InMemoryAsyncBus | None = None) -> None:
        self.bus = bus

    @asynccontextmanager
    async def trace(
        self,
        component: str,
        category: str = "operation",
        metadata: dict[str, Any] | None = None,
    ) -> AsyncGenerator[None, None]:
        """Async context manager tracing operation duration."""
        start_time = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            if self.bus:
                evt = TelemetryEvent(
                    event_id=f"tr-{int(start_time*1000)}",
                    event_type="telemetry",
                    category=category,
                    component=component,
                    duration_ms=duration_ms,
                    data=metadata or {},
                )
                self.bus.publish(evt)
