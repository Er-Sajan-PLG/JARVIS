"""Unit tests for app/adapters/websocket/stream.py."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.adapters.websocket.stream import websocket_endpoint, ws_router


@pytest.fixture
def mock_bootstrap():
    """Mock bootstrap_system at boundary."""
    with patch("app.adapters.websocket.stream.bootstrap_system") as mock_boot:
        container = MagicMock()
        analysis = MagicMock()
        analysis.complexity.value = "low"
        analysis.requires_tools = False
        container.intent_analyzer.analyze.return_value = analysis
        mock_boot.return_value = container
        yield mock_boot, container, analysis


@pytest.fixture
def client(mock_bootstrap):
    """Create a TestClient with ws_router."""
    app = FastAPI()
    app.include_router(ws_router)
    return TestClient(app)


def test_websocket_chat_endpoint_prompt_flow(client, mock_bootstrap):
    """Test websocket message flow with 'prompt' key."""
    _, container, analysis = mock_bootstrap
    analysis.complexity.value = "moderate"
    analysis.requires_tools = True

    with client.websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"prompt": "calculate pi"}))

        # 1. Intent analysis
        resp1 = ws.receive_json()
        assert resp1["type"] == "intent_analysis"
        assert resp1["complexity"] == "moderate"
        assert resp1["requires_tools"] is True

        # 2. Token chunk
        resp2 = ws.receive_json()
        assert resp2["type"] == "token_chunk"
        assert resp2["content"] == "Echo: calculate pi"

        # 3. Stream end
        resp3 = ws.receive_json()
        assert resp3["type"] == "stream_end"

    container.intent_analyzer.analyze.assert_called_with("calculate pi")


def test_websocket_root_endpoint_message_fallback(client, mock_bootstrap):
    """Test websocket endpoint at /ws using fallback 'message' key."""
    _, container, _ = mock_bootstrap

    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"message": "how are you?"}))

        resp1 = ws.receive_json()
        assert resp1["type"] == "intent_analysis"
        assert resp1["complexity"] == "low"
        assert resp1["requires_tools"] is False

        resp2 = ws.receive_json()
        assert resp2["type"] == "token_chunk"
        assert resp2["content"] == "Echo: how are you?"

        resp3 = ws.receive_json()
        assert resp3["type"] == "stream_end"

    container.intent_analyzer.analyze.assert_called_with("how are you?")


def test_websocket_empty_payload(client, mock_bootstrap):
    """Test websocket with empty JSON payload defaulting prompt to empty string."""
    _, container, _ = mock_bootstrap

    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({}))

        resp1 = ws.receive_json()
        assert resp1["type"] == "intent_analysis"

        resp2 = ws.receive_json()
        assert resp2["type"] == "token_chunk"
        assert resp2["content"] == "Echo: "

        resp3 = ws.receive_json()
        assert resp3["type"] == "stream_end"

    container.intent_analyzer.analyze.assert_called_with("")


@pytest.mark.asyncio
async def test_websocket_endpoint_handles_immediate_disconnect():
    """Directly test websocket_endpoint handling WebSocketDisconnect upon receive."""
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.receive_text.side_effect = WebSocketDisconnect(code=1000)

    with patch("app.adapters.websocket.stream.bootstrap_system") as mock_boot:
        mock_boot.return_value = MagicMock()
        # Should catch WebSocketDisconnect and return cleanly without raising
        await websocket_endpoint(mock_ws)

    mock_ws.accept.assert_awaited_once()
    mock_ws.receive_text.assert_awaited_once()


def test_sse_stream_endpoint_custom_prompt(client, mock_bootstrap):
    """Test SSE stream endpoint with a custom prompt query parameter."""
    _, container, analysis = mock_bootstrap
    analysis.complexity.value = "high"

    response = client.get("/ws/stream?prompt=write+a+poem")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    body = response.text
    assert 'data: {"type": "intent", "complexity": "high"}\n\n' in body
    assert (
        'data: {"type": "chunk", "content": "JARVIS streaming response for: write a poem"}\n\n'
        in body
    )
    assert "data: [DONE]\n\n" in body

    container.intent_analyzer.analyze.assert_called_with("write a poem")


def test_sse_stream_endpoint_default_prompt(client, mock_bootstrap):
    """Test SSE stream endpoint using default prompt 'hello'."""
    _, container, _ = mock_bootstrap

    response = client.get("/ws/stream")
    assert response.status_code == 200

    body = response.text
    assert 'data: {"type": "intent", "complexity": "low"}\n\n' in body
    assert 'data: {"type": "chunk", "content": "JARVIS streaming response for: hello"}\n\n' in body
    assert "data: [DONE]\n\n" in body

    container.intent_analyzer.analyze.assert_called_with("hello")
