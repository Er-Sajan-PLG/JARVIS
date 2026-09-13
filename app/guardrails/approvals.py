"""Human-in-the-Loop (HITL) Approval Registry.

Tracks ExecutionPlans that paused on a DESTRUCTIVE step awaiting human approval, and
records the resulting approve/deny decisions so a paused plan can be resumed.

This is the missing counterpart to ``ToolSafetyPolicy`` / ``ExecutionRunner``:
the runner *raises* ``HITLRequiredError`` and pauses the plan; this registry holds that
paused plan so an external actor (n8n → Slack/Telegram → ``POST /api/v1/hitl/approve``)
can decide, after which the plan is resumed.

State lives in memory. When a ``store_path`` is supplied it is additionally mirrored to
a JSON file, written atomically and re-read on construction, so a restart between a step
pausing and a human deciding does not silently drop the approval *and* the paused plan --
which is exactly what happened before this: the n8n polling loop saw an empty list, with
no error anywhere, and the request simply vanished.

Without ``store_path`` the registry stays pure in-process (no I/O), which is what the
majority of call sites and unit tests want, so persistence is opt-in and the default is
unchanged. It is intentionally *not* thread-safe; the FastAPI event loop is
single-threaded and all mutations happen there.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain import ExecutionPlan, ExecutionStep, SafetyTier, StepStatus, ToolCall

logger = logging.getLogger(__name__)

#: Valid values for a decision.
DECISION_APPROVE = "approve"
DECISION_DENY = "deny"


class ApprovalNotFoundError(KeyError):
    """Raised when no awaiting approval matches the given plan/step."""


class ApprovalAlreadyDecidedError(ValueError):
    """Raised when a decision is submitted twice for the same plan/step."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _step_to_dict(step: ExecutionStep) -> dict[str, Any]:
    """Serializable form of one execution step (the domain entity has none)."""
    call = step.tool_call
    return {
        "step_id": step.step_id,
        "title": step.title,
        "status": step.status.value,
        "error": step.error,
        "hitl_required": step.hitl_required,
        "hitl_approved": step.hitl_approved,
        "created_at": _iso(step.created_at),
        "tool_call": (
            {
                "tool_name": call.tool_name,
                "arguments": call.arguments,
                "safety_tier": call.safety_tier.value,
                "description": call.description,
            }
            if call is not None
            else None
        ),
    }


def _step_from_dict(raw: dict[str, Any]) -> ExecutionStep:
    call_raw = raw.get("tool_call")
    call = (
        ToolCall(
            tool_name=call_raw["tool_name"],
            arguments=call_raw.get("arguments", {}),
            safety_tier=SafetyTier(call_raw.get("safety_tier", SafetyTier.SAFE.value)),
            description=call_raw.get("description", ""),
        )
        if call_raw
        else None
    )
    return ExecutionStep(
        step_id=raw["step_id"],
        title=raw["title"],
        tool_call=call,
        status=StepStatus(raw.get("status", StepStatus.PENDING.value)),
        error=raw.get("error"),
        hitl_required=raw.get("hitl_required", False),
        hitl_approved=raw.get("hitl_approved"),
        created_at=_parse_dt(raw.get("created_at")) or _utcnow(),
    )


def _plan_to_dict(plan: ExecutionPlan) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "goal": plan.goal,
        "current_step_index": plan.current_step_index,
        "created_at": _iso(plan.created_at),
        "metadata": plan.metadata,
        "steps": [_step_to_dict(s) for s in plan.steps],
    }


def _plan_from_dict(raw: dict[str, Any]) -> ExecutionPlan:
    return ExecutionPlan(
        plan_id=raw["plan_id"],
        goal=raw.get("goal", ""),
        steps=[_step_from_dict(s) for s in raw.get("steps", [])],
        current_step_index=raw.get("current_step_index", 0),
        created_at=_parse_dt(raw.get("created_at")) or _utcnow(),
        metadata=raw.get("metadata", {}),
    )


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
    #: Set by the automation plane (n8n) once a human-facing notification was delivered,
    #: so a polling workflow does not re-announce the same approval on every tick.
    notified_at: datetime | None = None
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
            "notified_at": _iso(self.notified_at),
            "decided": self.decided,
            "decision": self.decision,
            "approver": self.approver,
            "reason": self.reason,
            "decided_at": _iso(self.decided_at),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PendingApproval":
        """Rebuild a record written by :meth:`to_dict`."""
        return cls(
            plan_id=raw["plan_id"],
            step_id=raw["step_id"],
            title=raw.get("title", ""),
            tool_name=raw.get("tool_name"),
            description=raw.get("description", ""),
            safety_tier=raw.get("safety_tier", "unknown"),
            requested_at=_parse_dt(raw.get("requested_at")) or _utcnow(),
            notified_at=_parse_dt(raw.get("notified_at")),
            decided=raw.get("decided", False),
            decision=raw.get("decision"),
            approver=raw.get("approver"),
            reason=raw.get("reason", ""),
            decided_at=_parse_dt(raw.get("decided_at")),
        )


@dataclass
class ApprovalRegistry:
    """Registry of paused plans and their approval decisions.

    Pass ``store_path`` to make the registry survive a process restart; omit it to
    keep the original pure in-process behaviour.
    """

    store_path: Path | None = None
    _plans: dict[str, ExecutionPlan] = field(default_factory=dict)
    _pending: dict[tuple[str, str], PendingApproval] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.store_path is not None:
            self.store_path = Path(self.store_path)
            self._load()

    # ------------------------------------------------------------------ storage

    def _load(self) -> None:
        """Read the store if it exists. A corrupt or absent store is not fatal."""
        assert self.store_path is not None
        if not self.store_path.is_file():
            return
        try:
            raw = json.loads(self.store_path.read_text(encoding="utf-8"))
            self._plans = {
                plan_id: _plan_from_dict(data) for plan_id, data in (raw.get("plans") or {}).items()
            }
            self._pending = {
                (rec["plan_id"], rec["step_id"]): PendingApproval.from_dict(rec)
                for rec in (raw.get("pending") or [])
            }
        except Exception as err:  # noqa: BLE001 - a bad store must not stop startup
            logger.error("Ignoring unreadable approval store %s: %s", self.store_path, err)
            self._plans = {}
            self._pending = {}

    def _save(self) -> None:
        """Mirror state to disk. No-op when no store path was configured."""
        if self.store_path is None:
            return
        payload = {
            "plans": {pid: _plan_to_dict(p) for pid, p in self._plans.items()},
            "pending": [r.to_dict() for r in self._pending.values()],
        }
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.store_path.with_name(self.store_path.name + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            tmp.replace(self.store_path)
        except OSError as err:
            # Persistence is a durability improvement, not a correctness gate: if the
            # disk is unavailable the in-process behaviour must still work.
            logger.error("Failed to persist approval store %s: %s", self.store_path, err)

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
        self._save()
        return records

    # --------------------------------------------------------------------- query

    def list_pending(self, *, include_decided: bool = False) -> list[PendingApproval]:
        """All tracked approvals, newest request first."""
        records = [r for r in self._pending.values() if include_decided or not r.decided]
        return sorted(records, key=lambda r: r.requested_at, reverse=True)

    def mark_notified(self, plan_id: str, step_id: str) -> PendingApproval:
        """Record that a human-facing notification was delivered for this approval.

        Idempotent — the first delivery timestamp wins, so a repeated delivery (or a
        polling workflow that re-sends) cannot keep extending the window. Raises
        ``ApprovalNotFoundError`` for an unknown plan/step.
        """
        record = self.get(plan_id, step_id)
        if record.notified_at is None:
            record.notified_at = _utcnow()
            self._save()
        return record

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
        self._save()
        return record
