"""Tests for the LangGraph cognitive engine (Sprint 3 Capability Contract)."""

from unittest.mock import MagicMock

import pytest

from app.brain import ExecutionRunner, IntentAnalyzer, TaskPlanner
from app.brain.graph import build_cognitive_graph, run_cognitive_loop
from app.domain import SafetyTier, StepStatus


@pytest.mark.asyncio
async def test_cognitive_graph_basic_flow():
    """The full cognitive loop runs intent -> plan -> execute -> synthesize -> evaluate."""
    analyzer = IntentAnalyzer()
    planner = TaskPlanner()
    runner = ExecutionRunner()

    result = await run_cognitive_loop("list files", analyzer, planner, runner)

    assert result["user_input"] == "list files"
    assert result["intent"] is not None
    assert result["plan"] is not None
    assert result["synthesized_response"] is not None
    assert result["next_node"] == "end"
    assert "quality_score" in result


@pytest.mark.asyncio
async def test_cognitive_graph_hitl_interrupt():
    """DESTRUCTIVE intent pauses the graph at the tool_executor node."""
    analyzer = IntentAnalyzer()
    planner = TaskPlanner()
    runner = ExecutionRunner()

    result = await run_cognitive_loop("create directory ./new_folder", analyzer, planner, runner)

    assert result["next_node"] == "interrupt"
    plan = result["plan"]
    assert plan is not None
    assert any(s.is_destructive for s in plan.steps)
    assert any(s.status == StepStatus.AWAITING_APPROVAL for s in plan.steps)


@pytest.mark.asyncio
async def test_cognitive_graph_hitl_resume():
    """Re-running with HITL approvals resumes past the DESTRUCTIVE step.

    Note: Each invocation creates a fresh plan with new step IDs (the planner
    generates UUID-based IDs). In production, LangGraph's checkpointer preserves
    the paused plan across invocations. For this test, we mock the planner to
    return a fixed plan so the step ID is stable.
    """
    from app.domain import ExecutionPlan, ExecutionStep, StepStatus, ToolCall

    analyzer = IntentAnalyzer()
    runner = ExecutionRunner()

    # Fixed plan with a known step ID
    fixed_step_id = "plan-fixed-s1"
    fixed_plan = ExecutionPlan(
        plan_id="plan-fixed",
        goal="create directory ./new_folder",
        steps=[
            ExecutionStep(
                step_id=fixed_step_id,
                title="Create directory ./new_folder (requires human approval)",
                tool_call=ToolCall(
                    tool_name="create_directory",
                    arguments={"path": "./new_folder"},
                    safety_tier=SafetyTier.DESTRUCTIVE,
                    description="Create directory",
                ),
                status=StepStatus.AWAITING_APPROVAL,
            ),
        ],
    )
    planner = MagicMock()
    planner.create_plan.return_value = fixed_plan

    # First run: pause at HITL (step already awaiting approval)
    result = await run_cognitive_loop("create directory ./new_folder", analyzer, planner, runner)
    assert result["next_node"] == "interrupt"

    # Second run: resume with approval for the known step ID
    result2 = await run_cognitive_loop(
        "create directory ./new_folder",
        analyzer,
        planner,
        runner,
        hitl_approvals={fixed_step_id: True},
    )
    assert result2["next_node"] == "end"
    assert result2["synthesized_response"] is not None


def test_build_cognitive_graph_returns_graph():
    """The graph builder returns a compiled graph when langgraph is installed."""
    analyzer = IntentAnalyzer()
    planner = TaskPlanner()
    runner = ExecutionRunner()

    graph = build_cognitive_graph(analyzer, planner, runner)
    assert graph is not None
