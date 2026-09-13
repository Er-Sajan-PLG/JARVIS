"""Unit tests for app/brain: analyzer, planner, runner, synthesizer, graph."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest

from app.brain.analyzer import IntentAnalysis, IntentAnalyzer, IntentComplexity
from app.brain.graph import (
    intent_analyzer_node,
    response_synthesizer_node,
    task_planner_node,
    tool_executor_node,
)
from app.brain.planner import (
    DESTRUCTIVE_DIR_TOOL,
    TaskPlanner,
    _destructive_path,
)
from app.brain.runner import ExecutionRunner
from app.brain.synthesizer import ResponseSynthesizer
from app.domain import (
    ExecutionPlan,
    ExecutionStep,
    IntentState,
    SafetyTier,
    StepStatus,
    ToolCall,
)
from app.events import HITLRequestEvent, InMemoryAsyncBus

# --- Analyzer Tests ---


def test_intent_analyzer_attachments() -> None:
    analyzer = IntentAnalyzer()
    res = analyzer.analyze("Summarize this", has_attachments=True)
    assert res.complexity == IntentComplexity.FILE_QUERY
    assert res.requires_tools is True
    assert "read_file" in res.suggested_tools


def test_intent_analyzer_multi_step() -> None:
    analyzer = IntentAnalyzer()
    res = analyzer.analyze("Please refactor the user authentication flow")
    assert res.complexity == IntentComplexity.MULTI_STEP
    assert res.requires_tools is True
    assert "file_tools" in res.suggested_tools


def test_intent_analyzer_tool_search() -> None:
    analyzer = IntentAnalyzer()
    res = analyzer.analyze("search for documentation on postgresql")
    assert res.complexity == IntentComplexity.TOOL_SEARCH
    assert res.requires_tools is True
    assert "search_web" in res.suggested_tools


def test_intent_analyzer_direct_chat() -> None:
    analyzer = IntentAnalyzer()
    res = analyzer.analyze("What is the capital of France?")
    assert res.complexity == IntentComplexity.DIRECT_CHAT
    assert res.requires_tools is False
    assert res.suggested_tools == []


# --- Planner Tests ---


def test_destructive_path_helper() -> None:
    # Destructive keyword + path
    assert _destructive_path("create directory /tmp/new_project") == "/tmp/new_project"
    # Note: strip includes '.' so './output/logs' becomes '/output/logs'
    assert _destructive_path("mkdir ./output/logs") == "/output/logs"

    # Destructive keyword but no path
    assert _destructive_path("create directory myfolder") is None

    # Path but no destructive keyword
    assert _destructive_path("inspect /tmp/new_project") is None


def test_task_planner_destructive_goal() -> None:
    planner = TaskPlanner()
    analysis = IntentAnalysis(complexity=IntentComplexity.MULTI_STEP, requires_tools=True)
    plan = planner.create_plan("mkdir /build/artifacts", analysis)

    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.tool_call is not None
    assert step.tool_call.tool_name == DESTRUCTIVE_DIR_TOOL
    assert step.tool_call.safety_tier == SafetyTier.DESTRUCTIVE
    assert step.tool_call.arguments == {"path": "/build/artifacts"}


def test_task_planner_direct_chat() -> None:
    planner = TaskPlanner()
    analysis = IntentAnalysis(complexity=IntentComplexity.DIRECT_CHAT)
    plan = planner.create_plan("Hello Jarvis", analysis)

    assert len(plan.steps) == 1
    assert plan.steps[0].tool_call is None
    assert plan.steps[0].title == "Generate direct response"


def test_task_planner_file_query() -> None:
    planner = TaskPlanner()
    analysis = IntentAnalysis(complexity=IntentComplexity.FILE_QUERY, requires_tools=True)
    plan = planner.create_plan("Summarize attached pdf", analysis)

    assert len(plan.steps) == 2
    assert plan.steps[0].tool_call is not None
    assert plan.steps[0].tool_call.tool_name == "read_file"
    assert plan.steps[1].tool_call is None


def test_task_planner_multi_step() -> None:
    planner = TaskPlanner()
    analysis = IntentAnalysis(complexity=IntentComplexity.MULTI_STEP, requires_tools=True)
    plan = planner.create_plan("Run audit on project", analysis)

    assert len(plan.steps) == 2
    assert plan.steps[0].tool_call is not None
    assert plan.steps[0].tool_call.tool_name == "list_dir"


# --- Runner Tests ---


@pytest.mark.asyncio
async def test_execution_runner_informational_step() -> None:
    runner = ExecutionRunner()
    step = ExecutionStep(step_id="s1", title="Synthesize", tool_call=None)
    plan = ExecutionPlan(plan_id="p1", goal="Test", steps=[step])

    executed_plan = await runner.execute_plan(plan)
    assert executed_plan.steps[0].status == StepStatus.COMPLETED


@pytest.mark.asyncio
async def test_execution_runner_sync_and_async_tools() -> None:
    runner = ExecutionRunner()

    def sync_calc(x: int) -> int:
        return x + 10

    async def async_fetch(url: str) -> str:
        return f"Fetched {url}"

    runner.register_tool("sync_calc", sync_calc)
    runner.register_tool("async_fetch", async_fetch)

    step1 = ExecutionStep(
        step_id="s1",
        title="Calc",
        tool_call=ToolCall(tool_name="sync_calc", arguments={"x": 5}),
    )
    step2 = ExecutionStep(
        step_id="s2",
        title="Fetch",
        tool_call=ToolCall(tool_name="async_fetch", arguments={"url": "http://api"}),
    )
    plan = ExecutionPlan(plan_id="p1", goal="Compute and Fetch", steps=[step1, step2])

    await runner.execute_plan(plan)
    assert step1.status == StepStatus.COMPLETED
    assert step1.result == 15
    assert step2.status == StepStatus.COMPLETED
    assert step2.result == "Fetched http://api"


@pytest.mark.asyncio
async def test_execution_runner_hitl_pause_and_resume() -> None:
    bus = InMemoryAsyncBus()
    hitl_events: list[HITLRequestEvent] = []

    async def hitl_collector(event: HITLRequestEvent) -> None:
        hitl_events.append(event)

    bus.subscribe("hitl_request", hitl_collector)

    runner = ExecutionRunner(event_bus=bus)
    runner.register_tool("delete_item", lambda target, **kw: f"Deleted {target}")

    step_destructive = ExecutionStep(
        step_id="s1",
        title="Delete",
        tool_call=ToolCall(
            tool_name="delete_item",
            arguments={"target": "database"},
            safety_tier=SafetyTier.DESTRUCTIVE,
            description="Drop DB",
        ),
    )
    plan = ExecutionPlan(plan_id="p_dest", goal="Delete DB", steps=[step_destructive])

    # 1. First execution pauses at HITL gate
    await runner.execute_plan(plan)
    await asyncio.sleep(0.01)
    assert step_destructive.status == StepStatus.AWAITING_APPROVAL
    assert step_destructive.hitl_required is True
    assert len(hitl_events) == 1
    assert hitl_events[0].tool_name == "delete_item"

    # 2. Resuming execution with explicit approval
    await runner.execute_plan(plan, hitl_approvals={"s1": True})
    assert step_destructive.status == StepStatus.COMPLETED
    assert step_destructive.result == "Deleted database"


@pytest.mark.asyncio
async def test_execution_runner_tool_failure() -> None:
    runner = ExecutionRunner()

    def buggy_tool() -> None:
        raise RuntimeError("Disk I/O error")

    runner.register_tool("buggy", buggy_tool)

    step = ExecutionStep(
        step_id="s1",
        title="Buggy step",
        tool_call=ToolCall(tool_name="buggy", arguments={}),
    )
    plan = ExecutionPlan(plan_id="p_err", goal="Fail", steps=[step])

    await runner.execute_plan(plan)
    assert step.status == StepStatus.FAILED
    assert "Disk I/O error" in str(step.error)


@pytest.mark.asyncio
async def test_execution_runner_skips_already_finished_steps() -> None:
    runner = ExecutionRunner()
    step_done = ExecutionStep(
        step_id="s0", title="Done", status=StepStatus.COMPLETED, result="already done"
    )
    step_skip = ExecutionStep(step_id="s1", title="Skipped", status=StepStatus.SKIPPED)
    step_next = ExecutionStep(step_id="s2", title="Next", tool_call=None)

    plan = ExecutionPlan(plan_id="p_seq", goal="Seq", steps=[step_done, step_skip, step_next])
    await runner.execute_plan(plan)

    assert step_done.result == "already done"
    assert step_next.status == StepStatus.COMPLETED


# --- Synthesizer Tests ---


@pytest.mark.asyncio
async def test_response_synthesizer_stream() -> None:
    synthesizer = ResponseSynthesizer()

    async def token_generator() -> AsyncGenerator[str, None]:
        tokens = ["Hello", " ", "world", "!"]
        for t in tokens:
            yield t

    collected = []
    async for chunk in synthesizer.synthesize_stream(token_generator()):
        collected.append(chunk)

    assert "".join(collected) == "Hello world!"


# --- Graph Nodes Tests ---


def test_brain_graph_nodes() -> None:
    # 1. intent_analyzer_node
    state_in: IntentState = {"prompt": "Hello", "session_id": "sess_1"}
    state_analyzed = intent_analyzer_node(state_in)
    assert "analysis" in state_analyzed
    assert state_analyzed["analysis"].complexity == IntentComplexity.DIRECT_CHAT

    # 2. task_planner_node
    with patch.object(
        TaskPlanner,
        "create_plan",
        return_value=ExecutionPlan(plan_id="p_test", goal="Hello"),
    ):
        state_planned = task_planner_node(state_analyzed)
        assert state_planned["plan"].plan_id == "p_test"
        assert state_planned["prompt"] == "Hello"

    # 3. tool_executor_node
    state_executed = tool_executor_node(state_planned)
    assert state_executed["executed"] == state_planned["plan"]
    assert state_executed["hitl_approvals"] == {}

    # 4. response_synthesizer_node
    state_response = response_synthesizer_node(state_executed)
    assert "synthesized" in state_response
    assert state_response["executed"] == state_executed["executed"]
