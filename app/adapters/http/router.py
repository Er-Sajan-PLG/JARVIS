"""HTTP Adapter Layer (REST API & Auth Security).

Exposes FastAPI HTTP routes secured with single-tenant Bearer Token / API Key
authentication (``JARVIS_API_KEY``), delegating execution to the app.bootstrap
Composition Root and the app.brain Cognitive Engine.
"""

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.adapters.http.synthesis import http_llm_enabled, synthesize_answer
from app.adapters.security import is_authorized
from app.bootstrap import ApplicationContainer, bootstrap_system
from app.config.version import VERSION as __version__
from app.domain import ExecutionPlan

# NB: app.adapters may only depend on app.bootstrap / app.brain (enforced by
# scripts/board/review.py `import_layering`). The HITL approval registry is reached
# through the container, so the two decision literals live here instead of being
# imported from app.guardrails.
DECISION_APPROVE = "approve"
DECISION_DENY = "deny"

http_router = APIRouter(prefix="/api/v1", tags=["JARVIS REST API"])


def _plan_status(plan: ExecutionPlan) -> str:
    """Human-readable lifecycle status for an ExecutionPlan."""
    if plan.is_complete:
        return "completed"
    return "failed" if plan.has_failed else "running"


async def validate_api_key(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> bool:
    """Single-tenant API Key / Bearer Token authentication dependency.

    Security model: if `JARVIS_API_KEY` is configured in the environment, every
    protected route requires a matching credential supplied either as
    `Authorization: Bearer <key>` or `X-API-Key: <key>`. If `JARVIS_API_KEY` is
    unset (local development), auth is disabled and all requests are allowed.
    """
    if is_authorized(authorization=authorization, x_api_key=x_api_key):
        return True
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@http_router.get("/health", tags=["System"])
async def health_check() -> dict[str, Any]:
    """Liveness probe & subsystem health snapshot."""
    container: ApplicationContainer = bootstrap_system()
    return {
        "status": "healthy",
        "service": "JARVIS",
        "version": __version__,
        "tools_registered": len(container.execution_runner._tool_registry),
    }


@http_router.get("/ready", tags=["System"])
async def readiness_check() -> dict[str, Any]:
    """Readiness probe: are the subsystems an answer depends on usable?

    Liveness (``/health``) asks "is the process up?"; readiness asks "should this
    instance receive traffic?". A container can be live while no model is
    resolvable — a chat request fails anyway, so the probe reports not-ready
    instead. Never raises: an unusable subsystem is reported as ``"down"`` with
    the reason, not as a 5xx.

    This checks the model path the request path actually uses
    (``adapters/web/settings.get_default`` + ``create_model_client``), not
    ``container.model_router``. The router is an abandoned abstraction: it has
    **zero** ``BaseLLMProvider`` implementations in the tree (verified — only
    ``MagicMock`` builds one), and its failover intent is already served by
    ``OmniModelClient`` over the ``ModelClient`` protocol that actually shipped.
    Reporting it here made the probe claim a subsystem was load-bearing when
    nothing reads it.
    """
    container: ApplicationContainer = bootstrap_system()
    checks: dict[str, str] = {}

    try:
        from app.adapters.web.settings import get_default

        default = get_default() or {}
        provider = default.get("provider") or ""
        model = default.get("model") or ""
        if not provider or not model:
            checks["model"] = "down: no default model selected (Settings → Model → Default Model)"
        elif provider == "agy":
            # CLI-backed pseudo-provider (app/adapters/integrations/agy.py). The
            # console reaches it directly; the HTTP path cannot, so readiness
            # reflects that split honestly instead of claiming either way.
            from app.adapters.integrations.agy import is_available as agy_available

            if agy_available():
                checks["model"] = f"ok: agy/{model} (console path only)"
            else:
                checks["model"] = "down: agy CLI not found on PATH"
        elif container.get_provider_spec(provider) is None:
            checks["model"] = f"down: default provider '{provider}' is not a known route"
        else:
            checks["model"] = f"ok: {provider}/{model}"
    except Exception as exc:  # noqa: BLE001 — a probe must answer, never raise
        checks["model"] = f"down: {exc}"

    checks["memory_service"] = "ok" if container.memory_service is not None else "down: not wired"
    checks["mode_manager"] = "ok" if container.mode_manager is not None else "down: not wired"

    ready = all(value.startswith("ok") for value in checks.values())
    return {"ready": ready, "checks": checks, "version": __version__}


@http_router.post("/chat/completions", dependencies=[Depends(validate_api_key)])
async def chat_completions(payload: dict[str, Any]) -> dict[str, Any]:
    """Primary synchronous cognitive loop endpoint.

    Pipeline: Intent Analysis -> Task Planning -> Execution -> Synthesis.
    Any DESTRUCTIVE step pauses for Human-in-the-Loop approval; the plan is then
    registered with the approval registry so it can be decided via
    POST /api/v1/hitl/approve and resumed.

    Migration Step 5: with ``JARVIS_HTTP_LLM=1`` the response also carries
    synthesized ``response`` text (see app/adapters/http/synthesis.py). With the
    flag off the payload is exactly what it has always been — plan status only —
    so existing HITL clients are unaffected either way.
    """
    container: ApplicationContainer = bootstrap_system()

    messages = payload.get("messages", [])
    prompt = ""
    if isinstance(messages, list) and messages:
        prompt = str(messages[-1].get("content", ""))
    elif "prompt" in payload:
        prompt = str(payload["prompt"])

    # NB: a missing prompt falls back to "" (contract: must not 500) — the cognitive
    # loop treats it as a direct-chat turn.
    session_id = payload.get("session_id", "default_session")

    # 1. Active Session & Conversation
    await container.session_manager.get_or_create_session(session_id)
    await container.session_manager.get_or_create_conversation(session_id=session_id)

    # 2. Intent Analysis & Plan
    analysis = container.intent_analyzer.analyze(prompt)
    plan = container.task_planner.create_plan(prompt, analysis)

    # 3. Execution
    executed_plan = await container.execution_runner.execute_plan(plan)

    # 4. Record metrics
    container.metrics.record_request()

    # 5. Register any DESTRUCTIVE step that paused for Human-in-the-Loop approval so it
    #    can be decided later via POST /api/v1/hitl/approve.
    awaiting = container.approval_registry.register_paused_plan(executed_plan)

    inner_analysis = analysis["analysis"] if isinstance(analysis, dict) else analysis
    response: dict[str, Any] = {
        "session_id": session_id,
        "plan_id": executed_plan.plan_id,
        "status": _plan_status(executed_plan),
        "steps_count": len(executed_plan.steps),
        "complexity": inner_analysis.complexity.value,
        "requires_tools": inner_analysis.requires_tools,
        "awaiting_approval": [item.to_dict() for item in awaiting],
    }

    # 6. Step 5 (flag-gated): synthesize the answer the plan does not contain.
    #    Additive only — failure adds ``synthesis_error`` instead of replacing
    #    the plan payload, so HITL consumers never lose their fields.
    if http_llm_enabled():
        response.update(await synthesize_answer(container, prompt, session_id))

    return response


@http_router.get("/hitl/pending", dependencies=[Depends(validate_api_key)])
async def hitl_pending(include_decided: bool = False) -> dict[str, Any]:
    """List DESTRUCTIVE steps currently awaiting Human-in-the-Loop approval."""
    container = bootstrap_system()
    records = container.approval_registry.list_pending(include_decided=include_decided)
    return {
        "count": len(records),
        "pending": [record.to_dict() for record in records],
    }


@http_router.post("/hitl/approve", dependencies=[Depends(validate_api_key)])
async def hitl_approve(payload: dict[str, Any]) -> dict[str, Any]:
    """Record a human approve/deny decision for a paused DESTRUCTIVE step and resume.

    Body:
        plan_id   (str, required)  - plan returned by /chat/completions or /hitl/pending
        step_id   (str, required)  - the step awaiting approval
        decision  (str)            - "approve" | "deny" (alias: approved: true/false)
        approver  (str)            - who decided (e.g. "slack:U0123" or "telegram:12345")
        reason    (str)            - optional justification, recorded on deny

    Approving re-queues the step and resumes the plan; denying skips the destructive
    step and resumes the remainder. A second decision for the same step returns 409.
    """
    plan_id = payload.get("plan_id")
    step_id = payload.get("step_id")
    if not plan_id or not step_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Both 'plan_id' and 'step_id' are required.",
        )

    # Accept either an explicit "decision" string or an "approved" boolean.
    raw_decision = payload.get("decision")
    if raw_decision is None:
        approved_flag = payload.get("approved")
        if approved_flag is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide 'decision' ('approve'|'deny') or 'approved' (true|false).",
            )
        raw_decision = DECISION_APPROVE if approved_flag else DECISION_DENY

    decision = str(raw_decision).strip().lower()
    if decision not in (DECISION_APPROVE, DECISION_DENY):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="'decision' must be 'approve' or 'deny'.",
        )

    approver = str(payload.get("approver") or "unknown")
    reason = str(payload.get("reason") or "")

    try:
        result = await _approve_pending_via_registry(
            str(plan_id), str(step_id), decision, approver=approver, reason=reason
        )
    except KeyError as err:
        # ApprovalNotFoundError subclasses KeyError — surface as 404.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except ValueError as err:
        # ApprovalAlreadyDecidedError subclasses ValueError — surface as 409.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err

    return result


async def _approve_pending_via_registry(
    plan_id: str,
    step_id: str,
    decision: str,
    *,
    approver: str = "unknown",
    reason: str = "",
) -> dict[str, Any]:
    """Decide a paused HITL approval and resume its plan. HTTP-free.

    Shared by the HTTP route and out-of-band channels (Telegram /approve,
    /deny). Raises KeyError (unknown) / ValueError (already decided).
    """
    container = bootstrap_system()
    registry = container.approval_registry

    approve = decision == DECISION_APPROVE
    record = registry.decide(plan_id, step_id, approve=approve, approver=approver, reason=reason)

    # Resume the plan. Approved steps execute; denied steps were set to SKIPPED and are
    # therefore passed over by the runner.
    plan = registry.get_plan(plan_id)
    resumed = await container.execution_runner.execute_plan(plan, hitl_approvals={step_id: approve})
    still_awaiting = registry.register_paused_plan(resumed)

    return {
        "decision": record.to_dict(),
        "plan_id": plan_id,
        "status": _plan_status(resumed),
        "steps_count": len(resumed.steps),
        "awaiting_approval": [item.to_dict() for item in still_awaiting],
    }


@http_router.post("/hitl/notified", dependencies=[Depends(validate_api_key)])
async def hitl_mark_notified(payload: dict[str, Any]) -> dict[str, Any]:
    """Record that the automation plane delivered a human-facing notification.

    Body: ``plan_id`` (str, required), ``step_id`` (str, required).

    Idempotent — the first timestamp wins. This is what stops a polling workflow (n8n
    every minute) from re-announcing the same approval on every tick; n8n's own workflow
    static data does not persist in this n8n build, so the marker lives with the approval
    state it describes.
    """
    container = bootstrap_system()

    plan_id = payload.get("plan_id")
    step_id = payload.get("step_id")
    if not plan_id or not step_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Both 'plan_id' and 'step_id' are required.",
        )

    try:
        record = container.approval_registry.mark_notified(str(plan_id), str(step_id))
    except KeyError as err:
        # ApprovalNotFoundError subclasses KeyError — surface as 404.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    return {"notified": record.to_dict()}
