"""Result of a tool execution within a cognitive loop turn."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.plan import SafetyTier


@dataclass
class ToolResult:
    """The outcome of a single tool execution, captured for the synthesizer and evaluator.

    Contract: docs/CAPABILITY-CONTRACT.md §1.1 CognitiveState.execution_results.
    """

    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    safety_tier: SafetyTier = SafetyTier.SAFE
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_provenance(self) -> dict[str, Any]:
        """Flatten to a provenance record for the synthesizer/evaluator."""
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "safety_tier": self.safety_tier.value,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
        }
