"""Tests for HITL approval: registry semantics + /api/v1/hitl endpoints.

Covers the full loop that n8n drives: a DESTRUCTIVE step pauses the plan
(AWAITING_APPROVAL), the approval registry records it, and a decision submitted over
HTTP either executes the step (approve) or skips it (deny).
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.bootstrap import bootstrap_system
from app.domain import ExecutionPlan, ExecutionStep, SafetyTier, StepStatus, ToolCall
from app.guardrails import (
    ApprovalAlreadyDecidedError,
    ApprovalNotFoundError,
    ApprovalRegistry,
)


def _destructive_plan(plan_id: str = "plan-hitl", path: str = "/tmp/doomed") -> ExecutionPlan:
    """A one-step plan whose only step is a DESTRUCTIVE tool call."""
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
            )
        ],
    )


# --------------------------------------------------------------------- registry


def test_registry_records_paused_destructive_step():
    registry = ApprovalRegistry()
    plan = _destructive_plan()
    plan.steps[0].status = StepStatus.AWAITING_APPROVAL

    records = registry.register_paused_plan(plan)

    assert len(records) == 1
    assert records[0].plan_id == "plan-hitl"
    assert records[0].step_id == "step-1"
    assert records[0].tool_name == "delete_file"
    assert records[0].safety_tier == "destructive"
    assert records[0].decided is False
    assert len(registry.list_pending()) == 1


def test_registry_ignores_plans_without_awaiting_steps():
    registry = ApprovalRegistry()
    plan = _destructive_plan()
    plan.steps[0].status = StepStatus.COMPLETED

    assert registry.register_paused_plan(plan) == []
    assert registry.list_pending() == []


def test_registry_register_is_idempotent_and_keeps_original_record():
    registry = ApprovalRegistry()
    plan = _destructive_plan()
    plan.steps[0].status = StepStatus.AWAITING_APPROVAL

    first = registry.register_paused_plan(plan)[0]
    second = registry.register_paused_plan(plan)[0]

    assert first is second
    assert len(registry.list_pending()) == 1


def test_registry_unknown_approval_raises():
    registry = ApprovalRegistry()
    with pytest.raises(ApprovalNotFoundError):
        registry.get("nope", "nope")


def test_registry_approve_sets_step_back_to_pending():
    registry = ApprovalRegistry()
    plan = _destructive_plan()
    plan.steps[0].status = StepStatus.AWAITING_APPROVAL
    registry.register_paused_plan(plan)

    record = registry.decide("plan-hitl", "step-1", approve=True, approver="tester")

    assert record.decided is True
    assert record.decision == "approve"
    assert plan.steps[0].hitl_approved is True
    assert plan.steps[0].status == StepStatus.PENDING
    assert registry.list_pending() == []


def test_registry_deny_skips_the_destructive_step():
    registry = ApprovalRegistry()
    plan = _destructive_plan()
    plan.steps[0].status = StepStatus.AWAITING_APPROVAL
    registry.register_paused_plan(plan)

    record = registry.decide(
        "plan-hitl", "step-1", approve=False, approver="tester", reason="not now"
    )

    assert record.decision == "deny"
    assert plan.steps[0].status == StepStatus.SKIPPED
    assert plan.steps[0].hitl_approved is False
    assert "not now" in (plan.steps[0].error or "")


def test_registry_double_decision_is_rejected():
    registry = ApprovalRegistry()
    plan = _destructive_plan()
    plan.steps[0].status = StepStatus.AWAITING_APPROVAL
    registry.register_paused_plan(plan)
    registry.decide("plan-hitl", "step-1", approve=True, approver="tester")

    with pytest.raises(ApprovalAlreadyDecidedError):
        registry.decide("plan-hitl", "step-1", approve=True, approver="tester")


# ------------------------------------------------------------------- HTTP API

API_KEY = "test-hitl-key"


@pytest.fixture
def client():
    """TestClient with a known JARVIS_API_KEY, plus a fresh registry and probe tool."""
    os.environ["JARVIS_API_KEY"] = API_KEY

    calls: list[dict] = []
    container = bootstrap_system()
    container.approval_registry._plans.clear()
    container.approval_registry._pending.clear()
    container.execution_runner.register_tool(
        # **_ mirrors the @safety_gate contract: the runner injects `_hitl_approved`,
        # which decorated tools pop. A tool that swallows it must accept **_.
        "delete_file",
        lambda path, **_: calls.append({"path": path}) or f"deleted {path}",
    )

    from app.main import app

    with TestClient(app) as test_client:
        test_client.calls = calls  # type: ignore[attr-defined]
        yield test_client

    os.environ.pop("JARVIS_API_KEY", None)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_KEY}"}


async def _pause_a_plan(plan_id: str) -> ExecutionPlan:
    """Run a destructive plan so it pauses, and register it for approval."""
    container = bootstrap_system()
    plan = _destructive_plan(plan_id=plan_id)
    executed = await container.execution_runner.execute_plan(plan)
    container.approval_registry.register_paused_plan(executed)
    return executed


def test_pending_requires_auth(client):
    assert client.get("/api/v1/hitl/pending").status_code == 401


def test_approve_requires_auth(client):
    response = client.post("/api/v1/hitl/approve", json={"plan_id": "p", "step_id": "s"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_destructive_plan_pauses_instead_of_executing(client):
    plan = await _pause_a_plan("plan-pause")

    assert plan.steps[0].status == StepStatus.AWAITING_APPROVAL
    assert plan.steps[0].hitl_required is True
    assert client.calls == [], "destructive tool must NOT run before approval"

    pending = client.get("/api/v1/hitl/pending", headers=_headers()).json()
    assert pending["count"] == 1
    assert pending["pending"][0]["step_id"] == "step-1"


@pytest.mark.asyncio
async def test_approve_executes_the_destructive_step(client):
    await _pause_a_plan("plan-approve")

    response = client.post(
        "/api/v1/hitl/approve",
        headers=_headers(),
        json={
            "plan_id": "plan-approve",
            "step_id": "step-1",
            "decision": "approve",
            "approver": "slack:U1",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["decision"]["decision"] == "approve"
    assert body["status"] == "completed"
    assert client.calls == [{"path": "/tmp/doomed"}], "approved tool should have run"
    assert client.get("/api/v1/hitl/pending", headers=_headers()).json()["count"] == 0


@pytest.mark.asyncio
async def test_deny_skips_the_destructive_step(client):
    await _pause_a_plan("plan-deny")

    response = client.post(
        "/api/v1/hitl/approve",
        headers=_headers(),
        json={
            "plan_id": "plan-deny",
            "step_id": "step-1",
            "approved": False,
            "approver": "slack:U1",
            "reason": "unsafe",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["decision"]["decision"] == "deny"
    assert client.calls == [], "denied tool must NOT run"


def test_unknown_plan_returns_404(client):
    response = client.post(
        "/api/v1/hitl/approve",
        headers=_headers(),
        json={"plan_id": "ghost", "step_id": "ghost", "decision": "approve"},
    )
    assert response.status_code == 404


def test_missing_fields_return_422(client):
    response = client.post("/api/v1/hitl/approve", headers=_headers(), json={"plan_id": "p"})
    assert response.status_code == 422


def test_bad_decision_returns_422(client):
    response = client.post(
        "/api/v1/hitl/approve",
        headers=_headers(),
        json={"plan_id": "p", "step_id": "s", "decision": "maybe"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_double_decision_returns_409(client):
    await _pause_a_plan("plan-twice")
    body = {"plan_id": "plan-twice", "step_id": "step-1", "decision": "approve"}

    assert client.post("/api/v1/hitl/approve", headers=_headers(), json=body).status_code == 200
    assert client.post("/api/v1/hitl/approve", headers=_headers(), json=body).status_code == 409


# ─── Notification marker (what stops the n8n poll re-announcing) ───────────────


def test_mark_notified_is_idempotent():
    registry = ApprovalRegistry()
    plan = _destructive_plan("plan-notify")
    plan.steps[0].status = StepStatus.AWAITING_APPROVAL  # else there is nothing to register
    registry.register_paused_plan(plan)

    first = registry.mark_notified("plan-notify", "step-1")
    assert first.notified_at is not None
    stamp = first.notified_at

    again = registry.mark_notified("plan-notify", "step-1")
    assert again.notified_at == stamp, "the first delivery timestamp must win"


def test_mark_notified_unknown_raises():
    registry = ApprovalRegistry()
    with pytest.raises(ApprovalNotFoundError):
        registry.mark_notified("nope", "nope")


@pytest.mark.asyncio
async def test_notified_at_is_reported_then_survives_a_decision(client):
    await _pause_a_plan("plan-notify-http")

    before = client.get("/api/v1/hitl/pending", headers=_headers()).json()["pending"][0]
    assert before["notified_at"] is None, "a fresh approval has not been announced yet"

    marked = client.post(
        "/api/v1/hitl/notified",
        headers=_headers(),
        json={"plan_id": "plan-notify-http", "step_id": "step-1"},
    )
    assert marked.status_code == 200
    assert marked.json()["notified"]["notified_at"] is not None

    # The marker is history, not state: deciding afterwards must not clear it.
    decided = client.post(
        "/api/v1/hitl/approve",
        headers=_headers(),
        json={"plan_id": "plan-notify-http", "step_id": "step-1", "decision": "deny"},
    )
    assert decided.status_code == 200


def test_notified_unknown_returns_404(client):
    response = client.post(
        "/api/v1/hitl/notified",
        headers=_headers(),
        json={"plan_id": "ghost", "step_id": "ghost"},
    )
    assert response.status_code == 404


def test_notified_missing_fields_returns_422(client):
    response = client.post("/api/v1/hitl/notified", headers=_headers(), json={"plan_id": "p"})
    assert response.status_code == 422
