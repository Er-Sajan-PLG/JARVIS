"""Step-by-Step ExecutionStep Runner.

Executes steps sequentially within an ExecutionPlan, enforcing safety policy evaluation,
triggering HITL approval gates for destructive steps, and emitting step status events to InMemoryAsyncBus.
"""

import inspect
import logging
from collections.abc import Callable
from typing import Any

from app.domain import ExecutionPlan, ExecutionStep, StepStatus
from app.events import HITLRequestEvent, InMemoryAsyncBus, StepExecutionEvent
from app.guardrails import HITLRequiredError, ToolSafetyPolicy

logger = logging.getLogger(__name__)


class ExecutionRunner:
    """Orchestrates step execution for an ExecutionPlan."""

    def __init__(
        self,
        event_bus: InMemoryAsyncBus | None = None,
        safety_policy: ToolSafetyPolicy | None = None,
    ) -> None:
        self.event_bus = event_bus or InMemoryAsyncBus()
        self.safety_policy = safety_policy or ToolSafetyPolicy()
        self._tool_registry: dict[str, Callable[..., Any]] = {}

    def register_tool(self, name: str, tool_func: Callable[..., Any]) -> None:
        """Register an atomic tool function with the runner."""
        self._tool_registry[name] = tool_func

    async def execute_plan(
        self, plan: ExecutionPlan, hitl_approvals: dict[str, bool] | None = None
    ) -> ExecutionPlan:
        """Execute all steps in an ExecutionPlan sequentially.

        Args:
            plan: The ExecutionPlan to execute.
            hitl_approvals: Optional mapping of step_id -> approved status.

        Returns:
            Updated ExecutionPlan instance.
        """
        hitl_approvals = hitl_approvals or {}

        for idx, step in enumerate(plan.steps):
            if step.status in (StepStatus.COMPLETED, StepStatus.SKIPPED):
                continue

            plan.current_step_index = idx
            await self._execute_step(
                plan.plan_id, step, hitl_approved=hitl_approvals.get(step.step_id)
            )

            if step.status == StepStatus.AWAITING_APPROVAL or step.status == StepStatus.FAILED:
                logger.info(
                    "Plan execution paused at step %s (Status: %s)", step.step_id, step.status.value
                )
                break

        return plan

    async def _execute_step(
        self, plan_id: str, step: ExecutionStep, hitl_approved: bool | None = None
    ) -> None:
        """Execute a single ExecutionStep."""
        step.status = StepStatus.IN_PROGRESS
        await self._notify_step(plan_id, step)

        if not step.tool_call:
            # Informational / LLM synthesis step
            step.status = StepStatus.COMPLETED
            await self._notify_step(plan_id, step)
            return

        tool_call = step.tool_call
        tool_name = tool_call.tool_name

        try:
            # 1. Safety Policy Evaluation
            self.safety_policy.evaluate_tool_call(
                tool_name=tool_name,
                tier=tool_call.safety_tier,
                args=tool_call.arguments,
                description=tool_call.description,
                hitl_approved=hitl_approved,
            )

            # 2. Invoke Tool if registered
            if tool_name in self._tool_registry:
                tool_func = self._tool_registry[tool_name]
                kwargs = dict(tool_call.arguments)
                if hitl_approved is not None:
                    kwargs["_hitl_approved"] = hitl_approved

                if inspect.iscoroutinefunction(tool_func):
                    res = await tool_func(**kwargs)
                else:
                    res = tool_func(**kwargs)
                    if inspect.iscoroutine(res):
                        res = await res
                step.result = res

            step.status = StepStatus.COMPLETED
            logger.info("Successfully executed step %s (%s)", step.step_id, tool_name)

        except HITLRequiredError as hitl_err:
            step.status = StepStatus.AWAITING_APPROVAL
            step.hitl_required = True
            step.error = str(hitl_err)

            # Publish HITL request event to passive bus
            hitl_event = HITLRequestEvent(
                event_id=f"hitl-{step.step_id}",
                event_type="hitl_request",
                plan_id=plan_id,
                step_id=step.step_id,
                title=step.title,
                tool_name=tool_name,
                arguments=tool_call.arguments,
                safety_tier=tool_call.safety_tier,
                description=tool_call.description,
            )
            self.event_bus.publish(hitl_event)

        except Exception as err:
            step.status = StepStatus.FAILED
            step.error = str(err)
            logger.exception("Step %s failed: %s", step.step_id, err)

        finally:
            await self._notify_step(plan_id, step)

    async def _notify_step(self, plan_id: str, step: ExecutionStep) -> None:
        """Publish step state transition event over InMemoryAsyncBus."""
        event = StepExecutionEvent(
            event_id=f"evt-{step.step_id}-{step.status.value}",
            event_type="step_execution",
            plan_id=plan_id,
            step_id=step.step_id,
            title=step.title,
            status=step.status,
            result=step.result,
            error=step.error,
        )
        self.event_bus.publish(event)
