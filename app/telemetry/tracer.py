"""Operation Latency & Context Tracer.

Measures execution duration for cognitive engine components and publishes
TelemetryEvents. When OTLP is enabled (via ``JARVIS_OTEL_ENABLED=true``),
spans are also shipped to an OTLP-compatible backend (Langfuse, ...).
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from app.events import InMemoryAsyncBus, TelemetryEvent

# OTel semantic convention attributes
OTEL_AGENT_NAME = "gen_ai.agent.name"
OTEL_TOOL_NAME = "gen_ai.tool.name"
OTEL_GUARDRAIL_RESULT = "gen_ai.guardrail.result"

logger = logging.getLogger(__name__)


class Tracer:
    """Measures execution duration and publishes TelemetryEvents over InMemoryAsyncBus.

    When ``otel_enabled=True``, also emits OTLP spans via :class:`OTLPExporter`.
    """

    def __init__(
        self,
        bus: InMemoryAsyncBus | None = None,
        *,
        otel_enabled: bool = False,
        otel_endpoint: str | None = None,
        otel_headers: dict[str, str] | None = None,
        otel_service_name: str | None = None,
    ) -> None:
        self.bus = bus
        self._otel_enabled = otel_enabled
        self._otlp_exporter: Any | None = None

        if otel_enabled:
            try:
                from app.telemetry.otel_exporter import OTLPExporter

                self._otlp_exporter = OTLPExporter(
                    endpoint=otel_endpoint,
                    headers=otel_headers,
                    service_name=otel_service_name,
                )
                if not self._otlp_exporter.enabled:
                    logger.warning("OTLPExporter not enabled — check opentelemetry SDK")
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to initialize OTLP exporter: %s", e)

    @asynccontextmanager
    async def trace(
        self,
        component: str,
        category: str = "operation",
        metadata: dict[str, Any] | None = None,
    ) -> AsyncGenerator[None, None]:
        """Async context manager tracing operation duration."""
        start_time = time.perf_counter()
        otlp_span_ctx = None
        otlp_span = None

        # Start OTLP span if enabled
        if self._otlp_exporter is not None and self._otlp_exporter.enabled:
            attrs = {
                OTEL_AGENT_NAME: "jarvis",
                "cognitive.component": component,
                "cognitive.category": category,
            }
            if metadata:
                for k, v in metadata.items():
                    attrs[f"cognitive.meta.{k}"] = str(v)
            otlp_span_ctx = self._otlp_exporter.start_span(component, attributes=attrs)
            otlp_span = otlp_span_ctx.__enter__()

        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # End OTLP span
            if otlp_span_ctx is not None and otlp_span is not None:
                with contextlib.suppress(Exception):
                    otlp_span_ctx.__exit__(None, None, None)

            # Publish local event
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
