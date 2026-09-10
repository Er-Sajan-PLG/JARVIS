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
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["system"].startswith("JARVIS")


def test_ready_returns_200_and_checks(client):
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert "model_router" in body["checks"]
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
    assert body["status"] in {"completed", "failed", "running"}


def test_chat_completions_missing_prompt_still_ok(client):
    # prompt falls back to empty string; should not 500
    r = client.post(
        "/api/v1/chat/completions",
        headers=_auth_headers(),
        json={"session_id": "no-prompt"},
    )
    assert r.status_code == 200


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