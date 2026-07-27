"""Unit tests for Phase 4: IntentAnalyzer, TaskPlanner, ExecutionRunner, ToolSafetyPolicy & @safety_gate.
"""

from pathlib import Path
import tempfile
import pytest

from app.brain import ExecutionRunner, IntentAnalyzer, IntentComplexity, TaskPlanner
from app.domain import SafetyTier, StepStatus
from app.events import InMemoryAsyncBus
from app.guardrails import HITLRequiredError, ToolSafetyPolicy
from app.tools import read_file, create_directory


def test_intent_analyzer() -> None:
    """Verify IntentAnalyzer classifies fast path vs tool search vs multi-step."""
    analyzer = IntentAnalyzer()

    # Fast path
    res1 = analyzer.analyze("Hello, how are you?")
    assert res1.complexity == IntentComplexity.DIRECT_CHAT
    assert res1.requires_tools is False

    # Multi-step
    res2 = analyzer.analyze("Refactor the repository and run tests")
    assert res2.complexity == IntentComplexity.MULTI_STEP
    assert res2.requires_tools is True

    # Attachment query
    res3 = analyzer.analyze("Summarize this document", has_attachments=True)
    assert res3.complexity == IntentComplexity.FILE_QUERY


def test_task_planner_and_runner_hitl() -> None:
    """Verify TaskPlanner builds ExecutionPlan and ExecutionRunner enforces HITL for destructive steps."""
    import asyncio

    async def _run() -> None:
        analyzer = IntentAnalyzer()
        planner = TaskPlanner()

        analysis = analyzer.analyze("Build new feature")
        plan = planner.create_plan("Build new feature", analysis)

        assert plan.plan_id.startswith("plan-")
        assert len(plan.steps) >= 2

        bus = InMemoryAsyncBus()
        hitl_events = []
        bus.subscribe("hitl_request", lambda e: hitl_events.append(e))

        policy = ToolSafetyPolicy(auto_approve_sensitive=True)
        runner = ExecutionRunner(event_bus=bus, safety_policy=policy)

        # Register destructive tool
        runner.register_tool("create_directory", create_directory)

        # Update step to trigger destructive tool
        plan.steps[0].tool_call.tool_name = "create_directory"
        plan.steps[0].tool_call.safety_tier = SafetyTier.DESTRUCTIVE

        # First run without approval: should pause with AWAITING_APPROVAL
        res_plan = await runner.execute_plan(plan)
        assert res_plan.steps[0].status == StepStatus.AWAITING_APPROVAL
        assert res_plan.steps[0].hitl_required is True

        # Second run with explicit HITL approval: should succeed
        with tempfile.TemporaryDirectory() as td:
            target_dir = Path(td) / "new_dir"
            plan.steps[0].tool_call.arguments = {"path": str(target_dir)}
            res_plan_approved = await runner.execute_plan(plan, hitl_approvals={plan.steps[0].step_id: True})
            assert res_plan_approved.steps[0].status == StepStatus.COMPLETED

    asyncio.run(_run())
