"""Unit tests for app/guardrails: ToolSafetyPolicy, ApprovalRegistry, safety_gate decorator."""

import pytest

from app.domain.plan import ExecutionPlan, ExecutionStep, SafetyTier, StepStatus, ToolCall
from app.guardrails.approvals import (
    DECISION_APPROVE,
    DECISION_DENY,
    ApprovalAlreadyDecidedError,
    ApprovalNotFoundError,
    ApprovalRegistry,
    PendingApproval,
)
from app.guardrails.decorator import safety_gate, set_global_policy
from app.guardrails.policy import HITLRequiredError, ToolSafetyPolicy


def test_tool_safety_policy_safe() -> None:
    policy = ToolSafetyPolicy()
    assert policy.evaluate_tool_call("read_file", SafetyTier.SAFE, {"path": "a.txt"}) is True


def test_tool_safety_policy_sensitive() -> None:
    # Auto approve sensitive True
    policy_auto = ToolSafetyPolicy(auto_approve_sensitive=True)
    assert (
        policy_auto.evaluate_tool_call("git_commit", SafetyTier.SENSITIVE, {"msg": "fix"}) is True
    )

    # Auto approve sensitive False without HITL approval
    policy_strict = ToolSafetyPolicy(auto_approve_sensitive=False)
    with pytest.raises(HITLRequiredError) as exc_info:
        policy_strict.evaluate_tool_call("git_commit", SafetyTier.SENSITIVE, {"msg": "fix"})
    assert exc_info.value.tool_name == "git_commit"
    assert "Sensitive operation requires confirmation" in exc_info.value.description

    # Auto approve sensitive False with HITL approval
    assert (
        policy_strict.evaluate_tool_call(
            "git_commit",
            SafetyTier.SENSITIVE,
            {"msg": "fix"},
            hitl_approved=True,
        )
        is True
    )


def test_tool_safety_policy_destructive() -> None:
    policy = ToolSafetyPolicy()

    # Destructive without approval raises HITLRequiredError
    with pytest.raises(HITLRequiredError) as exc_info:
        policy.evaluate_tool_call(
            "delete_file",
            SafetyTier.DESTRUCTIVE,
            {"path": "/tmp/test"},
            description="Deleting test file",
        )
    assert exc_info.value.tool_name == "delete_file"
    assert exc_info.value.description == "Deleting test file"
    assert "HITL approval required" in str(exc_info.value)

    # Destructive with approval proceeds
    assert (
        policy.evaluate_tool_call(
            "delete_file",
            SafetyTier.DESTRUCTIVE,
            {"path": "/tmp/test"},
            hitl_approved=True,
        )
        is True
    )


def test_pending_approval_to_dict() -> None:
    pending = PendingApproval(
        plan_id="p1",
        step_id="s1",
        title="Delete temp file",
        tool_name="delete_file",
        description="Permanently removes file",
        safety_tier="destructive",
    )
    data = pending.to_dict()
    assert data["plan_id"] == "p1"
    assert data["step_id"] == "s1"
    assert data["tool_name"] == "delete_file"
    assert data["decided"] is False
    assert data["notified_at"] is None
    assert "requested_at" in data


def test_approval_registry_workflow() -> None:
    registry = ApprovalRegistry()

    # Plan with no awaiting approval steps
    step_safe = ExecutionStep(
        step_id="s0",
        title="Read logs",
        tool_call=ToolCall(tool_name="read_file", safety_tier=SafetyTier.SAFE),
        status=StepStatus.COMPLETED,
    )
    plan_safe = ExecutionPlan(plan_id="p_safe", goal="safe run", steps=[step_safe])
    records = registry.register_paused_plan(plan_safe)
    assert records == []

    # Plan with awaiting approval step
    step_destructive = ExecutionStep(
        step_id="s1",
        title="Drop table",
        tool_call=ToolCall(
            tool_name="db_drop",
            safety_tier=SafetyTier.DESTRUCTIVE,
            description="Drops table from database",
        ),
        status=StepStatus.AWAITING_APPROVAL,
    )
    plan = ExecutionPlan(plan_id="p1", goal="cleanup", steps=[step_destructive])

    registered = registry.register_paused_plan(plan)
    assert len(registered) == 1
    assert registered[0].plan_id == "p1"
    assert registered[0].step_id == "s1"
    assert registered[0].tool_name == "db_drop"
    assert registered[0].description == "Drops table from database"
    assert registered[0].safety_tier == "destructive"

    # Idempotent re-registration returns existing record
    re_registered = registry.register_paused_plan(plan)
    assert re_registered[0] is registered[0]

    # get / get_plan
    assert registry.get("p1", "s1") is registered[0]
    assert registry.get_plan("p1") is plan

    # mark_notified
    assert registered[0].notified_at is None
    notified = registry.mark_notified("p1", "s1")
    assert notified.notified_at is not None
    first_notified_at = notified.notified_at
    # Idempotent mark_notified
    notified_again = registry.mark_notified("p1", "s1")
    assert notified_again.notified_at == first_notified_at

    # list_pending
    pending_list = registry.list_pending(include_decided=False)
    assert len(pending_list) == 1
    assert pending_list[0].step_id == "s1"


def test_approval_registry_decide_approve_and_deny() -> None:
    registry = ApprovalRegistry()

    # Create plan with 2 awaiting steps
    step1 = ExecutionStep(
        step_id="s1",
        title="Step 1",
        tool_call=ToolCall(tool_name="tool1", safety_tier=SafetyTier.DESTRUCTIVE),
        status=StepStatus.AWAITING_APPROVAL,
    )
    step2 = ExecutionStep(
        step_id="s2",
        title="Step 2",
        tool_call=ToolCall(tool_name="tool2", safety_tier=SafetyTier.DESTRUCTIVE),
        status=StepStatus.AWAITING_APPROVAL,
    )
    plan = ExecutionPlan(plan_id="p2", goal="run", steps=[step1, step2])
    registry.register_paused_plan(plan)

    # Approve step 1
    rec1 = registry.decide("p2", "s1", approve=True, approver="alice", reason="Looks good")
    assert rec1.decided is True
    assert rec1.decision == DECISION_APPROVE
    assert rec1.approver == "alice"
    assert rec1.reason == "Looks good"
    assert rec1.decided_at is not None
    assert step1.hitl_approved is True
    assert step1.hitl_required is True
    assert step1.status == StepStatus.PENDING
    assert step1.error is None

    # Deny step 2
    rec2 = registry.decide("p2", "s2", approve=False, approver="bob", reason="Too dangerous")
    assert rec2.decided is True
    assert rec2.decision == DECISION_DENY
    assert rec2.approver == "bob"
    assert step2.hitl_approved is False
    assert step2.status == StepStatus.SKIPPED
    assert step2.error == "Denied by bob: Too dangerous"

    # Already decided error
    with pytest.raises(ApprovalAlreadyDecidedError):
        registry.decide("p2", "s1", approve=True)

    # Query without decided
    assert len(registry.list_pending(include_decided=False)) == 0
    # Query with decided
    assert len(registry.list_pending(include_decided=True)) == 2


def test_approval_registry_errors() -> None:
    registry = ApprovalRegistry()
    with pytest.raises(ApprovalNotFoundError):
        registry.get("unknown_plan", "unknown_step")

    with pytest.raises(ApprovalNotFoundError):
        registry.get_plan("unknown_plan")

    with pytest.raises(ApprovalNotFoundError):
        registry.mark_notified("unknown_plan", "unknown_step")

    with pytest.raises(ApprovalNotFoundError):
        registry.decide("unknown_plan", "unknown_step", approve=True)


@pytest.mark.asyncio
async def test_safety_gate_decorator_sync_and_async() -> None:
    policy = ToolSafetyPolicy()
    set_global_policy(policy)

    @safety_gate(tier=SafetyTier.SAFE)
    def sync_safe_tool(x: int) -> int:
        return x * 2

    assert sync_safe_tool(5) == 10

    @safety_gate(tier=SafetyTier.DESTRUCTIVE, description="Wipe disk")
    def sync_destructive_tool(target: str) -> str:
        return f"Wiped {target}"

    # Fails without hitl approval
    with pytest.raises(HITLRequiredError):
        sync_destructive_tool(target="/dev/sda")

    # Succeeds with hitl approval passed as kwarg
    assert sync_destructive_tool(target="/dev/sda", _hitl_approved=True) == "Wiped /dev/sda"

    @safety_gate(tier=SafetyTier.SAFE)
    async def async_safe_tool(name: str) -> str:
        return f"Hello, {name}"

    assert await async_safe_tool("World") == "Hello, World"

    @safety_gate(tier=SafetyTier.DESTRUCTIVE, description="Drop db")
    async def async_destructive_tool(db_name: str) -> str:
        return f"Dropped {db_name}"

    with pytest.raises(HITLRequiredError):
        await async_destructive_tool(db_name="prod")

    assert await async_destructive_tool(db_name="prod", _hitl_approved=True) == "Dropped prod"
