"""Tiered Tool Safety Policy & Approval Rules.

Enforces 3 tiers:
  - SAFE: Automated pass-through (read-only file operations, search, OCR)
  - SENSITIVE: Rate-limit & policy validation checks (network, git commits)
  - DESTRUCTIVE: Mandatory Human-in-the-Loop (HITL) approval gate (file delete, terminal execution, DB writes)
"""

import logging
from typing import Any

from app.domain import SafetyTier

logger = logging.getLogger(__name__)


class PolicyViolationError(Exception):
    """Raised when a tool call violates a safety policy."""


class HITLRequiredError(Exception):
    """Raised when a DESTRUCTIVE tool call requires human approval before proceeding."""

    def __init__(self, tool_name: str, description: str, args: dict[str, Any]) -> None:
        self.tool_name = tool_name
        self.description = description
        self.args = args
        super().__init__(
            f"HITL approval required for destructive tool '{tool_name}': {description}"
        )


class ToolSafetyPolicy:
    """Policy engine enforcing security and approval boundaries for tool execution."""

    def __init__(self, auto_approve_sensitive: bool = True) -> None:
        self.auto_approve_sensitive = auto_approve_sensitive
        self._pending_approvals: dict[str, dict[str, Any]] = {}

    def evaluate_tool_call(
        self,
        tool_name: str,
        tier: SafetyTier,
        args: dict[str, Any],
        description: str = "",
        hitl_approved: bool | None = None,
    ) -> bool:
        """Evaluate if a tool call is permitted to execute.

        Args:
            tool_name: Name of the tool.
            tier: Safety tier of the tool call.
            args: Tool invocation arguments.
            description: Description of the action.
            hitl_approved: Explicit HITL approval flag (if user approved via UI/API).

        Returns:
            True if permitted to execute.

        Raises:
            HITLRequiredError: If destructive operation requires user approval.
            PolicyViolationError: If operation is rejected by policy.
        """
        logger.info("Evaluating safety policy for tool '%s' (Tier: %s)", tool_name, tier.value)

        if tier == SafetyTier.SAFE:
            return True

        if tier == SafetyTier.SENSITIVE:
            # Check basic validation
            if not self.auto_approve_sensitive and hitl_approved is not True:
                raise HITLRequiredError(
                    tool_name, description or "Sensitive operation requires confirmation", args
                )
            return True

        if tier == SafetyTier.DESTRUCTIVE:
            if hitl_approved is True:
                logger.info("HITL approval verified for destructive tool '%s'", tool_name)
                return True
            # Mandatory HITL Gate
            raise HITLRequiredError(
                tool_name=tool_name,
                description=description or f"Destructive operation '{tool_name}' requires approval",
                args=args,
            )

        return True
