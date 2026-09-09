"""HTTP Adapter Layer (REST API & Auth Security).

Exposes FastAPI HTTP routes secured with single-tenant Bearer Token / API Key authentication (`JARVIS_API_KEY`),
delegating execution to app.bootstrap Composition Root and app.brain Cognitive Engine.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import os
from typing import Any

from app.bootstrap import bootstrap_system

http_router = APIRouter(prefix="/api/v1", tags=["REST API"])
security_bearer = HTTPBearer(auto_error=False)


async def validate_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> str:
    """Validate single-tenant API Key from Bearer token or X-API-Key header."""
    expected_key = os.getenv("JARVIS_API_KEY")
    if not expected_key:
        return "development"

    provided_key: str | None = None
    if credentials:
        provided_key = credentials.credentials
    elif x_api_key:
        provided_key = x_api_key

    if not provided_key or provided_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing JARVIS_API_KEY authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return provided_key


@http_router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    container = bootstrap_system()
    return {
        "status": "healthy",
        "system": "JARVIS v3.0",
        "providers_registered": list(container.model_router.providers.keys()),
    }


@http_router.post("/chat/completions", dependencies=[Depends(validate_api_key)])
async def chat_completions(payload: dict[str, Any]) -> dict[str, Any]:
    """Process chat completion request through Cognitive Brain."""
    container = bootstrap_system()
    prompt = payload.get("prompt", payload.get("message", ""))
    session_id = payload.get("session_id", "default_session")

    # 1. Active Session & Conversation
    session = await container.session_manager.get_or_create_session(session_id)
    conversation = await container.session_manager.get_or_create_conversation(session_id=session_id)

    # 2. Intent Analysis & Plan
    analysis = container.intent_analyzer.analyze(prompt)
    plan = container.task_planner.create_plan(prompt, analysis)

    # 3. Execution
    executed_plan = await container.execution_runner.execute_plan(plan)

    # 4. Record metrics
    container.metrics.record_request()

    return {
        "session_id": session_id,
        "plan_id": executed_plan.plan_id,
        "status": "completed" if executed_plan.is_complete else ("failed" if executed_plan.has_failed else "running"),
        "steps_count": len(executed_plan.steps),
        "complexity": analysis.complexity.value,
    }
