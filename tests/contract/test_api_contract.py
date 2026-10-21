"""Contract tests for JARVIS HTTP/WS adapters.

Verifies the public API surface matches the documented contract in
docs/API_CONTRACT.md. These tests exercise the real FastAPI app via
TestClient, not mocks, so they fail loudly if an endpoint's shape
drifts from the contract.
"""

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Build a TestClient against the real app/main.py app."""
    mod = importlib.import_module("app.main")
    # Re-import to escape any prior singleton state
    importlib.reload(mod)
    with TestClient(mod.app) as c:
        yield c


def _auth_headers() -> dict:
    """Auth headers — dev mode allows any key when JARVIS_API_KEY unset."""
    return {"Authorization": "Bearer dev-test-key"}


# ─── Health / liveness ───────────────────────────────────────────────────────


def test_health_returns_200_and_shape(client):
    """Contract: docs/API_CONTRACT.md §3.1 — GET /api/v1/health, no auth.

    Shape is {status, service, version, tools_registered}
    (app/adapters/http/router.py:51-60). The router mounts under the
    /api/v1 prefix (app/main.py:154), so the bare path is not a route.
    """
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["service"] == "JARVIS"
    assert body["version"].startswith("v")
    assert isinstance(body["tools_registered"], int)


def test_health_requires_no_auth(client, monkeypatch):
    """Contract: health is a liveness probe and must not depend on the API key."""
    monkeypatch.setenv("JARVIS_API_KEY", "correct-key")
    r = client.get("/api/v1/health")
    assert r.status_code == 200


def test_ready_returns_200_and_checks(client):
    """Contract: GET /api/v1/ready reports per-subsystem readiness.

    Readiness (not liveness): the subsystems an answer depends on must be
    reported by name. The probe is total — it answers 200 with a per-check
    verdict rather than 5xx, so a caller always learns which part is down
    (app/adapters/http/router.py:64-112).

    The model check follows the request path (a resolvable default model), not
    ``container.model_router``, which has no provider implementations.
    """
    r = client.get("/api/v1/ready")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["ready"], bool)
    assert "model" in body["checks"]
    assert "memory_service" in body["checks"]


# ─── REST chat completions ───────────────────────────────────────────────────


def test_chat_completions_contract_shape(client):
    r = client.post(
        "/api/v1/chat/completions",
        headers=_auth_headers(),
        json={"prompt": "Hello JARVIS", "session_id": "contract-test"},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) >= {"session_id", "plan_id", "status", "steps_count", "complexity"}
    assert body["session_id"] == "contract-test"
    assert isinstance(body["steps_count"], int)
    # Not `in {"completed", "failed", "running"}`. That set made the test
    # unsatisfiable-to-fail: the endpoint could answer status="failed" with
    # steps_count=0 -- the chat path doing nothing at all -- and the assertion
    # still passed, because "failed" was one of the accepted values (F-TEST-010).
    # A valid prompt must complete, and completing means at least one step ran.
    assert body["status"] == "completed", f"a valid prompt did not complete: {body['status']!r}"
    assert body["steps_count"] >= 1, "reported completed with zero steps executed"


def test_chat_completions_missing_prompt_still_ok(client):
    # prompt falls back to empty string; should not 500
    r = client.post(
        "/api/v1/chat/completions",
        headers=_auth_headers(),
        json={"session_id": "no-prompt"},
    )
    assert r.status_code == 200


def test_chat_completions_omits_response_text_when_flag_off(client, monkeypatch):
    """Migration Step 5: with JARVIS_HTTP_LLM off, no synthesized text is added.

    This is the compatibility guarantee for HITL consumers (n8n JARVIS-HITL.json,
    Telegram /approve resume) that read plan status and would misread a text field.
    """
    monkeypatch.delenv("JARVIS_HTTP_LLM", raising=False)
    r = client.post(
        "/api/v1/chat/completions",
        headers=_auth_headers(),
        json={"prompt": "hello", "session_id": "flag-off"},
    )
    assert r.status_code == 200
    assert "response" not in r.json()
    assert "synthesis_error" not in r.json()


def test_chat_completions_with_flag_on_keeps_plan_fields(client, monkeypatch):
    """Flag on is ADDITIVE: every plan field survives alongside the answer.

    Synthesis is allowed to fail here (no live model in CI) — the assertion is
    that a synthesis outcome never removes the plan payload the endpoint has
    always returned.
    """
    monkeypatch.setenv("JARVIS_HTTP_LLM", "1")
    r = client.post(
        "/api/v1/chat/completions",
        headers=_auth_headers(),
        json={"prompt": "hello", "session_id": "flag-on"},
    )
    assert r.status_code == 200
    body = r.json()

    # Plan fields are unconditional.
    assert set(body.keys()) >= {
        "session_id",
        "plan_id",
        "status",
        "steps_count",
        "complexity",
        "requires_tools",
        "awaiting_approval",
    }
    # Exactly one synthesis outcome is present: an answer or a reason there isn't one.
    assert ("response" in body) ^ ("synthesis_error" in body)


# ─── Auth enforcement ────────────────────────────────────────────────────────


def test_chat_completions_requires_auth_when_key_set(client, monkeypatch):
    monkeypatch.setenv("JARVIS_API_KEY", "correct-key")
    # No auth header → 401
    r = client.post(
        "/api/v1/chat/completions",
        json={"prompt": "x", "session_id": "s"},
    )
    assert r.status_code == 401


def test_chat_completions_wrong_key_401(client, monkeypatch):
    monkeypatch.setenv("JARVIS_API_KEY", "correct-key")
    r = client.post(
        "/api/v1/chat/completions",
        headers={"Authorization": "Bearer wrong-key"},
        json={"prompt": "x", "session_id": "s"},
    )
    assert r.status_code == 401


# ─── Streaming (SSE) ─────────────────────────────────────────────────────────


def test_sse_stream_emits_intent_and_done(client):
    r = client.get("/ws/stream", params={"prompt": "hello"})
    assert r.status_code == 200
    body = r.text
    assert "intent" in body
    assert "[DONE]" in body
