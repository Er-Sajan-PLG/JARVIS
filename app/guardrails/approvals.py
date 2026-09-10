"""Human-in-the-Loop (HITL) Approval Registry.

Tracks ExecutionPlans that paused on a DESTRUCTIVE step awaiting human approval, and
records the resulting approve/deny decisions so a paused plan can be resumed.

This is the missing counterpart to ``ToolSafetyPolicy`` / ``ExecutionRunner``:
the runner *raises* ``HITLRequiredError`` and pauses the plan; this registry holds that
paused plan so an external actor (n8n → Slack/Telegram → ``POST /api/v1/hitl/approve``)
can decide, after which the plan is resumed.

Pure in-process state (no I/O), so it is trivially testable. It is intentionally *not*
thread-safe; the FastAPI event loop is single-threaded and all mutations happen there.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain import ExecutionPlan, ExecutionStep, StepStatus

#: Valid values for a decision.
DECISION_APPROVE = "approve"
DECISION_DENY = "deny"


class ApprovalNotFoundError(KeyError):
    """Raised when no awaiting approval matches the given plan/step."""


class ApprovalAlreadyDecidedError(ValueError):
    """Raised when a decision is submitted twice for the same plan/step."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class PendingApproval:
    """A single DESTRUCTIVE step awaiting a human decide-or-deny decision."""

    plan_id: str
    step_id: str
    title: str
    tool_name: str | None
    description: str
    safety_tier: str
    requested_at: datetime = field(default_factory=_utcnow)
    decided: bool = False
    decision: str | None = None
    approver: str | None = None
    reason: str = ""
    decided_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializable representation (used by the REST API)."""
        return {
            "plan_id": self.plan_id,
            "step_id": self.step_id,
            "title": self.title,
            "tool_name": self.tool_name,
            "description": self.description,
            "safety_tier": self.safety_tier,
            "requested_at": self.requested_at.isoformat(),
            "decided": self.decided,
            "decision": self.decision,
            "approver": self.approver,
            "reason": self.reason,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
        }


@dataclass
class ApprovalRegistry:
    """In-process registry of paused plans and their approval decisions."""

    _plans: dict[str, ExecutionPlan] = field(default_factory=dict)
    _pending: dict[tuple[str, str], PendingApproval] = field(default_factory=dict)

    # ------------------------------------------------------------------ register

    def register_paused_plan(self, plan: ExecutionPlan) -> list[PendingApproval]:
        """Record every step of ``plan`` that is awaiting approval.

        Returns the (possibly pre-existing) PendingApproval records for that plan.
        Idempotent: re-registering an already-tracked, still-undecided step keeps the
        original record (and its original ``requested_at``).
        """
        awaiting = [s for s in plan.steps if s.status == StepStatus.AWAITING_APPROVAL]
        if not awaiting:
            return []

        self._plans[plan.plan_id] = plan
        records: list[PendingApproval] = []
        for step in awaiting:
            key = (plan.plan_id, step.step_id)
            existing = self._pending.get(key)
            if existing is not None and not existing.decided:
                records.append(existing)
                continue
            tool_call = step.tool_call
            record = PendingApproval(
                plan_id=plan.plan_id,
                step_id=step.step_id,
                title=step.title,
                tool_name=tool_call.tool_name if tool_call else None,
                description=(tool_call.description if tool_call else None) or step.title,
                safety_tier=(tool_call.safety_tier.value if tool_call else "unknown"),
            )
            self._pending[key] = record
            records.append(record)
        return records

    # --------------------------------------------------------------------- query

    def list_pending(self, *, include_decided: bool = False) -> list[PendingApproval]:
        """All tracked approvals, newest request first."""
        records = [r for r in self._pending.values() if include_decided or not r.decided]
        return sorted(records, key=lambda r: r.requested_at, reverse=True)

    def get(self, plan_id: str, step_id: str) -> PendingApproval:
        """Fetch one approval record, or raise ``ApprovalNotFoundError``."""
        try:
            return self._pending[(plan_id, step_id)]
        except KeyError as err:
            raise ApprovalNotFoundError(
                f"No pending approval for plan_id={plan_id!r} step_id={step_id!r}"
            ) from err

    def get_plan(self, plan_id: str) -> ExecutionPlan:
        """Fetch the paused plan, or raise ``ApprovalNotFoundError``."""
        try:
            return self._plans[plan_id]
        except KeyError as err:
            raise ApprovalNotFoundError(f"Unknown plan_id={plan_id!r}") from err

    # -------------------------------------------------------------------- decide

    def decide(
        self,
        plan_id: str,
        step_id: str,
        *,
        approve: bool,
        approver: str = "unknown",
        reason: str = "",
    ) -> PendingApproval:
        """Record a decision and apply it to the paused plan's step.

        Approving sets ``step.hitl_approved = True`` and returns the step to PENDING so
        the runner will execute it on resume. Denying marks the step SKIPPED with the
        reason, so a resume continues past it instead of executing a destructive action.

        Raises ApprovalNotFoundError / ApprovalAlreadyDecidedError.
        """
        record = self.get(plan_id, step_id)
        if record.decided:
            raise ApprovalAlreadyDecidedError(
                f"plan_id={plan_id!r} step_id={step_id!r} already decided "
                f"({record.decision!r} by {record.approver!r})"
            )

        step: ExecutionStep | None = next(
            (s for s in self._plans[plan_id].steps if s.step_id == step_id), None
        )

        if approve:
            record.decision = DECISION_APPROVE
            if step is not None:
                step.hitl_approved = True
                step.hitl_required = True
                step.status = StepStatus.PENDING
                step.error = None
        else:
            record.decision = DECISION_DENY
            if step is not None:
                step.hitl_approved = False
                step.status = StepStatus.SKIPPED
                step.error = (
                    f"Denied by {approver}: {reason}" if reason else f"Denied by {approver}"
                )

        record.decided = True
        record.approver = approver
        record.reason = reason
        record.decided_at = _utcnow()
        return record
