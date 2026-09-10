"""JARVIS Guardrails Package.

Provides tool safety policy enforcement, tiered security validation, and @safety_gate decorator.
"""

from app.guardrails.approvals import (
    DECISION_APPROVE,
    DECISION_DENY,
    ApprovalAlreadyDecidedError,
    ApprovalNotFoundError,
    ApprovalRegistry,
    PendingApproval,
)
from app.guardrails.decorator import safety_gate, set_global_policy
from app.guardrails.policy import HITLRequiredError, PolicyViolationError, ToolSafetyPolicy

__all__ = [
    "ToolSafetyPolicy",
    "PolicyViolationError",
    "HITLRequiredError",
    "safety_gate",
    "set_global_policy",
    "ApprovalRegistry",
    "PendingApproval",
    "ApprovalNotFoundError",
    "ApprovalAlreadyDecidedError",
    "DECISION_APPROVE",
    "DECISION_DENY",
]
