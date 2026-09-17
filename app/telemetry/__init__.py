"""JARVIS Telemetry Package.

Provides observability, structured event logging, tracing, and metrics aggregation.
"""

from app.telemetry.logger import OTEL_AGENT_NAME, OTEL_GUARDRAIL_RESULT, OTEL_TOOL_NAME, EventLogger
from app.telemetry.metrics import (
    OTEL_AGENT_NAME as METRICS_OTEL_AGENT_NAME,
    OTEL_GUARDRAIL_RESULT as METRICS_OTEL_GUARDRAIL_RESULT,
    OTEL_TOOL_NAME as METRICS_OTEL_TOOL_NAME,
    AggregatedMetrics,
    MetricsCollector,
)
from app.telemetry.tracer import (
    OTEL_AGENT_NAME as TRACER_OTEL_AGENT_NAME,
    OTEL_GUARDRAIL_RESULT as TRACER_OTEL_GUARDRAIL_RESULT,
    OTEL_TOOL_NAME as TRACER_OTEL_TOOL_NAME,
    Tracer,
)

__all__ = [
    "EventLogger",
    "Tracer",
    "AggregatedMetrics",
    "MetricsCollector",
    "OTEL_AGENT_NAME",
    "OTEL_TOOL_NAME",
    "OTEL_GUARDRAIL_RESULT",
]
