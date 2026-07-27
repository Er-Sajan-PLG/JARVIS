"""Safety Gate Decorator for Tool Execution.

Wraps atomic tool functions to enforce safety policy evaluation prior to execution.
"""

from functools import wraps
import inspect
import logging
from typing import Any, Callable, TypeVar

from app.domain import SafetyTier
from app.guardrails.policy import ToolSafetyPolicy

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

_global_policy = ToolSafetyPolicy()


def set_global_policy(policy: ToolSafetyPolicy) -> None:
    """Set the active global tool safety policy."""
    global _global_policy
    _global_policy = policy


def safety_gate(
    tier: SafetyTier = SafetyTier.SAFE,
    description: str = "",
) -> Callable[[F], F]:
    """Decorator to enforce safety gates on tool functions.

    Usage:
        @safety_gate(tier=SafetyTier.DESTRUCTIVE, description="Delete file on disk")
        async def delete_file(path: str) -> bool:
            ...
    """

    def decorator(func: F) -> F:
        tool_name = func.__name__

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                hitl_approved = kwargs.pop("_hitl_approved", None)
                _global_policy.evaluate_tool_call(
                    tool_name=tool_name,
                    tier=tier,
                    args=kwargs,
                    description=description or func.__doc__ or tool_name,
                    hitl_approved=hitl_approved,
                )
                return await func(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]
        else:
            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                hitl_approved = kwargs.pop("_hitl_approved", None)
                _global_policy.evaluate_tool_call(
                    tool_name=tool_name,
                    tier=tier,
                    args=kwargs,
                    description=description or func.__doc__ or tool_name,
                    hitl_approved=hitl_approved,
                )
                return func(*args, **kwargs)

            return sync_wrapper  # type: ignore[return-value]

    return decorator
