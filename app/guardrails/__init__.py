"""JARVIS Guardrails Package.

Provides tool safety policy enforcement, tiered security validation, and @safety_gate decorator.
"""

from app.guardrails.decorator import safety_gate, set_global_policy
from app.guardrails.policy import HITLRequiredError, PolicyViolationError, ToolSafetyPolicy

__all__ = [
    "ToolSafetyPolicy",
    "PolicyViolationError",
    "HITLRequiredError",
    "safety_gate",
    "set_global_policy",
]
