"""Safety flag raised during intent analysis.

When a user intent is classified as touching a DESTRUCTIVE operation, the intent
analyzer raises a SafetyFlag. The tool_executor node consults these flags to route
DESTRUCTIVE steps through the HITL gate — a human must approve before execution.

Contract: docs/CAPABILITY-CONTRACT.md §1.2 (intent_analyzer output),
           §1.3 (interrupt() on DESTRUCTIVE is mandatory).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.plan import SafetyTier


@dataclass
class SafetyFlag:
    """Raised when a user intent involves a safety-sensitive operation.

    Consumed by: task_planner (marks the matching step with the tier),
                 tool_executor (routes DESTRUCTIVE to HITL).
    """

    tier: SafetyTier
    reason: str
    tool_name: str | None = None
    arguments: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_destructive(self) -> bool:
        """Only DESTRUCTIVE-tier flags require HITL approval."""
        return self.tier == SafetyTier.DESTRUCTIVE
