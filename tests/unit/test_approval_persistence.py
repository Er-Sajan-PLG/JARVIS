"""ApprovalRegistry persistence tests (Phase 0 finding F5).

The registry held paused HITL approvals in process memory only, so a restart
between a DESTRUCTIVE step pausing and a human deciding dropped the approval
*and* the paused plan. The n8n loop that polls ``/api/v1/hitl/pending`` would
then see an empty list with no error anywhere -- the request simply vanished.

Measured before this change: a second ``ApprovalRegistry`` saw nothing.

These tests pin that a registry given a store path reloads pending approvals,
decisions, notification markers, and the paused plans themselves -- and that the
default (no path) stays pure in-process, because 13 call sites construct it with
no arguments.
"""

import json

import pytest

from app.domain import ExecutionPlan, ExecutionStep, SafetyTier, StepStatus, ToolCall
from app.guardrails import ApprovalAlreadyDecidedError, ApprovalRegistry


def _paused_plan(plan_id: str = "plan-hitl", path: str = "/tmp/doomed") -> ExecutionPlan:
    """A one-step plan paused on a DESTRUCTIVE tool call."""
    return ExecutionPlan(
        plan_id=plan_id,
        goal="delete a temp file",
        steps=[
            ExecutionStep(
                step_id="step-1",
                title="Delete temp file",
                tool_call=ToolCall(
                    tool_name="delete_file",
                    arguments={"path": path},
                    safety_tier=SafetyTier.DESTRUCTIVE,
                    description=f"Permanently delete {path}",
                ),
                status=StepStatus.AWAITING_APPROVAL,
            )
        ],
    )


# --------------------------------------------------------------- pending survives


def test_pending_approval_survives_restart(tmp_path):
    store = tmp_path / "approvals.json"
    first = ApprovalRegistry(store_path=store)
    first.register_paused_plan(_paused_plan())
    assert first.list_pending()[0].decided is False

    second = ApprovalRegistry(store_path=store)
    pending = second.list_pending()
    assert len(pending) == 1
    assert pending[0].plan_id == "plan-hitl"
    assert pending[0].step_id == "step-1"
    assert pending[0].tool_name == "delete_file"
    assert pending[0].safety_tier == "destructive"


def test_decision_survives_restart(tmp_path):
    store = tmp_path / "approvals.json"
    first = ApprovalRegistry(store_path=store)
    first.register_paused_plan(_paused_plan())
    first.decide("plan-hitl", "step-1", approve=True, approver="slack:U1")

    second = ApprovalRegistry(store_path=store)
    assert second.list_pending() == []
    record = second.get("plan-hitl", "step-1")
    assert record.decided is True
    assert record.decision == "approve"
    assert record.approver == "slack:U1"
    assert record.decided_at is not None


def test_paused_plan_survives_restart_so_decide_can_still_resume(tmp_path):
    """Persisting the record is not enough: decide() must reach the actual plan."""
    store = tmp_path / "approvals.json"
    first = ApprovalRegistry(store_path=store)
    first.register_paused_plan(_paused_plan())

    second = ApprovalRegistry(store_path=store)
    second.decide("plan-hitl", "step-1", approve=True, approver="n8n")

    step = second.get_plan("plan-hitl").steps[0]
    assert step.hitl_approved is True
    assert step.status == StepStatus.PENDING


def test_deny_survives_restart(tmp_path):
    store = tmp_path / "approvals.json"
    first = ApprovalRegistry(store_path=store)
    first.register_paused_plan(_paused_plan())
    first.decide("plan-hitl", "step-1", approve=False, approver="n8n", reason="not now")

    second = ApprovalRegistry(store_path=store)
    step = second.get_plan("plan-hitl").steps[0]
    assert step.status == StepStatus.SKIPPED
    assert "not now" in (step.error or "")


def test_reload_preserves_requested_at_and_idempotency(tmp_path):
    store = tmp_path / "approvals.json"
    first = ApprovalRegistry(store_path=store)
    original = first.register_paused_plan(_paused_plan())[0]

    second = ApprovalRegistry(store_path=store)
    again = second.register_paused_plan(_paused_plan())[0]
    assert again.requested_at == original.requested_at


def test_notified_marker_survives_restart(tmp_path):
    store = tmp_path / "approvals.json"
    first = ApprovalRegistry(store_path=store)
    first.register_paused_plan(_paused_plan())
    marked = first.mark_notified("plan-hitl", "step-1")

    second = ApprovalRegistry(store_path=store)
    assert second.get("plan-hitl", "step-1").notified_at == marked.notified_at


def test_tool_arguments_survive_restart(tmp_path):
    """The resumed step must still carry the exact tool arguments."""
    store = tmp_path / "approvals.json"
    ApprovalRegistry(store_path=store).register_paused_plan(_paused_plan(path="/tmp/exact-arg"))

    second = ApprovalRegistry(store_path=store)
    call = second.get_plan("plan-hitl").steps[0].tool_call
    assert call is not None
    assert call.tool_name == "delete_file"
    assert call.arguments == {"path": "/tmp/exact-arg"}
    assert call.safety_tier == SafetyTier.DESTRUCTIVE


# --------------------------------------------------------------- in-memory default


def test_default_registry_is_in_memory_and_writes_nothing(tmp_path, monkeypatch):
    """No path => pure in-process, exactly as before (13 call sites rely on it)."""
    monkeypatch.chdir(tmp_path)
    registry = ApprovalRegistry()
    assert registry.store_path is None

    registry.register_paused_plan(_paused_plan())
    registry.decide("plan-hitl", "step-1", approve=True)

    assert list(tmp_path.rglob("*.json")) == []
    assert ApprovalRegistry().list_pending() == []


# --------------------------------------------------------------- robustness


def test_missing_store_directory_is_created(tmp_path):
    store = tmp_path / "nested" / "deeper" / "approvals.json"
    ApprovalRegistry(store_path=store).register_paused_plan(_paused_plan())
    assert store.exists()


def test_store_is_valid_json(tmp_path):
    store = tmp_path / "approvals.json"
    ApprovalRegistry(store_path=store).register_paused_plan(_paused_plan())
    json.loads(store.read_text(encoding="utf-8"))  # must not raise


def test_corrupt_store_is_ignored_not_fatal(tmp_path):
    """A truncated store must not make the app unstartable."""
    store = tmp_path / "approvals.json"
    store.write_text("{not json", encoding="utf-8")

    registry = ApprovalRegistry(store_path=store)
    assert registry.list_pending() == []


def test_double_decision_is_still_rejected_after_reload(tmp_path):
    """Durability must not lose the already-decided guard."""
    store = tmp_path / "approvals.json"
    ApprovalRegistry(store_path=store).register_paused_plan(_paused_plan())

    second = ApprovalRegistry(store_path=store)
    second.decide("plan-hitl", "step-1", approve=True, approver="first")

    third = ApprovalRegistry(store_path=store)
    with pytest.raises(ApprovalAlreadyDecidedError):
        third.decide("plan-hitl", "step-1", approve=True, approver="second")
