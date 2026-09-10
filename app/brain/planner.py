"""Slow-Path Dynamic Task Planner.

Generates inspectable, serializable ExecutionPlans containing ordered collections of
discrete ExecutionStep domain models.
"""

import logging
import uuid
from typing import Any

from app.brain.analyzer import IntentAnalysis, IntentComplexity
from app.domain import ExecutionPlan, ExecutionStep, SafetyTier, StepStatus, ToolCall

logger = logging.getLogger(__name__)


# Sprint 3 capability (ADR-006, AGENTS.md §5): node skeleton.
# Full execution graph definition with typed-state routing is NEXT increment.
NODE_FLOW = ("intent_analyzer", "task_planner", "tool_executor", "response_synthesizer")

# ─── Destructive-intent routing (ADR-011) ──────────────────────────────────────────
# `create_directory` is the only DESTRUCTIVE-tier tool, so it is the sole route into the
# HITL gate. Keyword routing is intentionally conservative — a creating verb AND a
# path-like token — so an ambiguous prompt never pauses the loop or invents a target.
DESTRUCTIVE_DIR_TOOL = "create_directory"
DESTRUCTIVE_KEYWORDS = (
    "create directory",
    "make directory",
    "create dir",
    "make dir",
    "create folder",
    "make folder",
    "new directory",
    "new folder",
    "mkdir",
)


def _destructive_path(goal: str) -> str | None:
    """Return a path-like argument when the goal asks for a directory to be created."""
    lowered = goal.lower()
    if not any(keyword in lowered for keyword in DESTRUCTIVE_KEYWORDS):
        return None
    for token in goal.replace(",", " ").split():
        cleaned = token.strip("\"'`()[]{}:;.")
        if cleaned.startswith(("/", "./", "../", "~")) or "/" in cleaned:
            return cleaned
    return None


class TaskPlanner:
    """Dynamic Task Planner generating inspectable ExecutionPlans."""

    def create_plan(
        self,
        goal: str,
        analysis: IntentAnalysis,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionPlan:
        """Construct an ExecutionPlan based on intent analysis.

        Args:
            goal: User goal or prompt.
            analysis: IntentAnalysis from analyzer.
            metadata: Optional metadata.

        Returns:
            ExecutionPlan domain model.
        """
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        steps: list[ExecutionStep] = []

        # A plan can only reach the HITL gate if it contains a DESTRUCTIVE step (ADR-011).
        destructive_path = _destructive_path(goal)

        if destructive_path:
            steps.append(
                ExecutionStep(
                    step_id=f"{plan_id}-s1",
                    title=f"Create directory {destructive_path} (requires human approval)",
                    tool_call=ToolCall(
                        tool_name=DESTRUCTIVE_DIR_TOOL,
                        arguments={"path": destructive_path},
                        safety_tier=SafetyTier.DESTRUCTIVE,
                        description=f"Create directory {destructive_path}",
                    ),
                    status=StepStatus.PENDING,
                )
            )
        elif analysis.complexity == IntentComplexity.DIRECT_CHAT:
            steps.append(
                ExecutionStep(
                    step_id=f"{plan_id}-s1",
                    title="Generate direct response",
                    tool_call=None,
                    status=StepStatus.PENDING,
                )
            )
        elif analysis.complexity == IntentComplexity.FILE_QUERY:
            steps.append(
                ExecutionStep(
                    step_id=f"{plan_id}-s1",
                    title="Inspect & extract attachments",
                    tool_call=ToolCall(
                        tool_name="read_file",
                        arguments={"path": "attachments"},
                        safety_tier=SafetyTier.SAFE,
                        description="Read attached files",
                    ),
                    status=StepStatus.PENDING,
                )
            )
            steps.append(
                ExecutionStep(
                    step_id=f"{plan_id}-s2",
                    title="Synthesize response from content",
                    tool_call=None,
                    status=StepStatus.PENDING,
                )
            )
        else:
            # Multi-step complex plan
            steps.append(
                ExecutionStep(
                    step_id=f"{plan_id}-s1",
                    title="Analyze workspace context",
                    tool_call=ToolCall(
                        tool_name="list_dir",
                        arguments={"path": "."},
                        safety_tier=SafetyTier.SAFE,
                        description="Explore workspace directory",
                    ),
                    status=StepStatus.PENDING,
                )
            )
            steps.append(
                ExecutionStep(
                    step_id=f"{plan_id}-s2",
                    title="Execute task steps",
                    tool_call=None,
                    status=StepStatus.PENDING,
                )
            )

        logger.info(
            "Generated ExecutionPlan %s with %d steps for goal: %s", plan_id, len(steps), goal[:50]
        )
        return ExecutionPlan(
            plan_id=plan_id,
            goal=goal,
            steps=steps,
            metadata=metadata or {},
        )
