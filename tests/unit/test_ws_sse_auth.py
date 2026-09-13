"""Auth enforcement tests for the WebSocket / SSE streaming adapters.

Phase 0 finding F4: ``ws_router`` carried no authentication while the HTTP
router did. Measured before this change: with ``JARVIS_API_KEY`` configured,
``GET /ws/stream`` returned 200 and an anonymous WS upgrade to ``/ws/chat``
was accepted.

These tests pin the required behaviour:

* when ``JARVIS_API_KEY`` is configured, an unauthenticated WS upgrade or SSE
  request is refused;
* a correct credential supplied as a header OR as a query parameter is
  accepted -- browsers cannot set headers on ``WebSocket`` or ``EventSource``,
  so header-only auth would break the real client;
* when ``JARVIS_API_KEY`` is unset (local development) behaviour is unchanged.
"""

import importlib
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.adapters.websocket.stream import ws_router

API_KEY = "correct-key"


@pytest.fixture
def app_client():
    """A TestClient carrying only the streaming router."""
    app = FastAPI()
    app.include_router(ws_router)
    return TestClient(app)


@pytest.fixture
def mock_bootstrap():
    """Patch bootstrap_system at the module boundary."""
    with patch("app.adapters.websocket.stream.bootstrap_system") as mock_boot:
        container = MagicMock()
        analysis = MagicMock()
        analysis.complexity.value = "low"
        analysis.requires_tools = False
        container.intent_analyzer.analyze.return_value = analysis
        mock_boot.return_value = container
        yield container


# ─── WebSocket ───────────────────────────────────────────────────────────────


def test_ws_rejects_missing_credential(app_client, monkeypatch):
    """An anonymous upgrade must be refused when a key is configured."""
    monkeypatch.setenv("JARVIS_API_KEY", API_KEY)
    with pytest.raises(WebSocketDisconnect) as exc, app_client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"prompt": "hi"}))
        ws.receive_json()
    assert exc.value.code == 1008, f"expected policy-violation close, got {exc.value.code}"


def test_ws_rejects_wrong_credential(app_client, monkeypatch):
    """A wrong key must be refused, not silently accepted."""
    monkeypatch.setenv("JARVIS_API_KEY", API_KEY)
    with (
        pytest.raises(WebSocketDisconnect) as exc,
        app_client.websocket_connect("/ws/chat?api_key=wrong-key") as ws,
    ):
        ws.send_text(json.dumps({"prompt": "hi"}))
        ws.receive_json()
    assert exc.value.code == 1008


def test_ws_accepts_credential_via_query_param(app_client, mock_bootstrap, monkeypatch):
    """EventSource/WebSocket cannot set headers -- the query param must work."""
    monkeypatch.setenv("JARVIS_API_KEY", API_KEY)
    with app_client.websocket_connect(f"/ws/chat?api_key={API_KEY}") as ws:
        ws.send_text(json.dumps({"prompt": "hi"}))
        assert ws.receive_json()["type"] == "intent_analysis"


def test_ws_accepts_credential_via_authorization_header(app_client, mock_bootstrap, monkeypatch):
    """Non-browser clients keep the same Bearer contract as the HTTP surface."""
    monkeypatch.setenv("JARVIS_API_KEY", API_KEY)
    with app_client.websocket_connect(
        "/ws/chat", headers={"Authorization": f"Bearer {API_KEY}"}
    ) as ws:
        ws.send_text(json.dumps({"prompt": "hi"}))
        assert ws.receive_json()["type"] == "intent_analysis"


def test_ws_accepts_credential_via_x_api_key_header(app_client, mock_bootstrap, monkeypatch):
    """X-API-Key is the documented alternative to Bearer on the HTTP surface."""
    monkeypatch.setenv("JARVIS_API_KEY", API_KEY)
    with app_client.websocket_connect("/ws/chat", headers={"X-API-Key": API_KEY}) as ws:
        ws.send_text(json.dumps({"prompt": "hi"}))
        assert ws.receive_json()["type"] == "intent_analysis"


def test_ws_dev_mode_allows_anonymous_when_key_unset(app_client, mock_bootstrap, monkeypatch):
    """With no key configured, local development keeps working (no regression)."""
    monkeypatch.delenv("JARVIS_API_KEY", raising=False)
    with app_client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"prompt": "hi"}))
        assert ws.receive_json()["type"] == "intent_analysis"


# ─── SSE ─────────────────────────────────────────────────────────────────────


def test_sse_rejects_missing_credential(app_client, monkeypatch):
    """SSE is an HTTP GET on the same router -- it must be gated too."""
    monkeypatch.setenv("JARVIS_API_KEY", API_KEY)
    assert app_client.get("/ws/stream?prompt=hello").status_code == 401


def test_sse_rejects_wrong_credential(app_client, monkeypatch):
    monkeypatch.setenv("JARVIS_API_KEY", API_KEY)
    assert app_client.get("/ws/stream?prompt=hello&api_key=wrong-key").status_code == 401


def test_sse_accepts_credential_via_query_param(app_client, mock_bootstrap, monkeypatch):
    monkeypatch.setenv("JARVIS_API_KEY", API_KEY)
    r = app_client.get(f"/ws/stream?prompt=hello&api_key={API_KEY}")
    assert r.status_code == 200
    assert "[DONE]" in r.text


def test_sse_accepts_credential_via_authorization_header(app_client, mock_bootstrap, monkeypatch):
    monkeypatch.setenv("JARVIS_API_KEY", API_KEY)
    r = app_client.get("/ws/stream?prompt=hello", headers={"Authorization": f"Bearer {API_KEY}"})
    assert r.status_code == 200


def test_sse_dev_mode_allows_anonymous_when_key_unset(app_client, mock_bootstrap, monkeypatch):
    monkeypatch.delenv("JARVIS_API_KEY", raising=False)
    assert app_client.get("/ws/stream?prompt=hello").status_code == 200


# ─── Real application (end-to-end) ───────────────────────────────────────────


def test_real_app_sse_requires_auth(monkeypatch):
    """Prove the gate holds on the composed app, not just the isolated router."""
    monkeypatch.setenv("JARVIS_API_KEY", API_KEY)
    mod = importlib.import_module("app.main")
    with TestClient(mod.app) as client:
        assert client.get("/ws/stream?prompt=hello").status_code == 401
        ok = client.get(f"/ws/stream?prompt=hello&api_key={API_KEY}")
        assert ok.status_code == 200
