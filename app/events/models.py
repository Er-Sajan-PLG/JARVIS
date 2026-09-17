"""Strongly-Typed Event Contracts for Passive Cross-Cutting Concerns.

Used exclusively by InMemoryAsyncBus for telemetry, logging, metrics, background jobs, SSE events, and scheduler alerts.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain import SafetyTier, StepStatus


@dataclass
class Event:
    """Base event contract."""

    event_id: str
    event_type: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TelemetryEvent(Event):
    """Telemetry, tracing, and metric collection event."""

    category: str = "telemetry"
    component: str = "system"
    duration_ms: float | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepExecutionEvent(Event):
    """Event emitted during execution step transitions in the Cognitive Engine."""

    plan_id: str = ""
    step_id: str = ""
    title: str = ""
    status: StepStatus = StepStatus.PENDING
    result: Any | None = None
    error: str | None = None


@dataclass
class HITLRequestEvent(Event):
    """Event published when a DESTRUCTIVE step requires Human-in-the-Loop approval."""

    plan_id: str = ""
    step_id: str = ""
    title: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    safety_tier: SafetyTier = SafetyTier.DESTRUCTIVE
    description: str = ""


@dataclass
class TokenUsageEvent(Event):
    """Event tracking token consumption and estimated costs."""

    provider: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


@dataclass
class NotificationEvent(Event):
    """System notification event (e.g. background job finish, scheduler alert)."""

    title: str = ""
    message: str = ""
    level: str = "info"  # info, warning, error
