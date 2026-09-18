"""Pure Domain Entities: Inspectable Execution Plans & Steps.

Zero infrastructure or framework dependencies. Modern Python 3.11+ syntax.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class SafetyTier(str, Enum):
    """Safety classification tier for tool execution."""

    SAFE = "safe"  # Read-only operations, automated pass-through
    SENSITIVE = "sensitive"  # Network requests, git commits, automated checks
    DESTRUCTIVE = "destructive"  # File deletion, terminal commands, mandatory HITL approval


class StepStatus(str, Enum):
    """Lifecycle state of an execution step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ToolCall:
    """Specification of a tool invocation within a plan step."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    safety_tier: SafetyTier = SafetyTier.SAFE
    description: str = ""


@dataclass
class ExecutionStep:
    """Discrete, serializable step within an ExecutionPlan."""

    step_id: str
    title: str
    tool_call: ToolCall | None = None
    status: StepStatus = StepStatus.PENDING
    result: Any | None = None
    error: str | None = None
    hitl_required: bool = False
    hitl_approved: bool | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_destructive(self) -> bool:
        """True if the tool call is classified as DESTRUCTIVE safety tier."""
        return bool(self.tool_call and self.tool_call.safety_tier == SafetyTier.DESTRUCTIVE)


@dataclass
class ExecutionPlan:
    """Ordered collection of discrete ExecutionSteps produced by the Brain Planner."""

    plan_id: str
    goal: str
    steps: list[ExecutionStep] = field(default_factory=list)
    current_step_index: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """Check if all steps are completed or skipped."""
        return all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in self.steps)

    @property
    def has_failed(self) -> bool:
        """Check if any step has failed."""
        return any(s.status == StepStatus.FAILED for s in self.steps)

    @property
    def current_step(self) -> ExecutionStep | None:
        """Get the currently active step, if any."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
