"""Unit tests for app/models/anthropic_client.py."""

import pytest
import requests
from requests.exceptions import RequestException

from app.models.anthropic_client import AnthropicClient
from app.models.exceptions import (
    ModelConnectionError,
    ModelResponseError,
)


def test_constructor_success():
    client = AnthropicClient(model="claude-3-haiku-20240307", api_key="test-key", role="analysis")
    assert client.model_name == "claude-3-haiku-20240307"
    assert client.role == "analysis"
    assert client._headers["x-api-key"] == "test-key"
    assert client._headers["anthropic-version"] == "2023-06-01"
    assert client._headers["content-type"] == "application/json"


def test_constructor_missing_key():
    with pytest.raises(ValueError, match="Anthropic requires an API key"):
        AnthropicClient(model="claude-3-haiku-20240307", api_key="")


def test_constructor_default_role():
    client = AnthropicClient(model="claude-3-haiku-20240307", api_key="k")
    assert client.role == "general"


def test_convert_messages():
    client = AnthropicClient(model="m", api_key="k")
    messages = [
        {"role": "system", "content": "System instruction 1"},
        {"role": "system", "content": "System instruction 2"},
        {"role": "user", "content": "Hello"},
        {"role": "user", "content": "world"},  # Consecutive user message should merge
        {"role": "assistant", "content": "Hi there"},
        {"role": "user", "content": ""},  # Empty message should be skipped
    ]
    system, converted = client._convert_messages(messages)
    assert system == "System instruction 1\n\nSystem instruction 2"
    assert converted == [
        {"role": "user", "content": "Hello\n\nworld"},
        {"role": "assistant", "content": "Hi there"},
    ]


def test_convert_messages_no_system():
    client = AnthropicClient(model="m", api_key="k")
    system, converted = client._convert_messages([{"role": "user", "content": "Hi"}])
    assert system is None
    assert converted == [{"role": "user", "content": "Hi"}]


def test_generate_sync_success(monkeypatch):
    client = AnthropicClient(model="claude-3-haiku", api_key="k")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "content": [
                    {"type": "text", "text": "Anthropic says hi!"},
                    {"type": "other", "data": "ignore me"},
                ],
                "usage": {"input_tokens": 10, "output_tokens": 15},
                "stop_reason": "end_turn",
            }

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    resp = client.generate(
        [
            {"role": "system", "content": "be concise"},
            {"role": "user", "content": "hello"},
        ],
        stream=False,
        max_tokens=500,
        temperature=0.7,
        top_p=0.9,
        top_k=40,
    )

    assert resp.content == "Anthropic says hi!"
    assert resp.model == "claude-3-haiku"
    assert resp.tokens_used == 25
    assert resp.finish_reason == "end_turn"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["json"]["max_tokens"] == 500
    assert captured["json"]["temperature"] == 0.7
    assert captured["json"]["top_p"] == 0.9
    assert captured["json"]["top_k"] == 40
    assert captured["json"]["system"] == "be concise"


def test_generate_sync_connection_error(monkeypatch):
    client = AnthropicClient(model="claude-3-haiku", api_key="k")

    def fake_post(*args, **kwargs):
        raise RequestException("Network unreachable")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(ModelConnectionError, match="Could not reach Anthropic"):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_sync_malformed_json(monkeypatch):
    client = AnthropicClient(model="claude-3-haiku", api_key="k")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            raise ValueError("Invalid JSON response")

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse())

    with pytest.raises(ModelResponseError, match="Malformed response from Anthropic"):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_sync_api_error_in_body(monkeypatch):
    client = AnthropicClient(model="claude-3-haiku", api_key="k")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"error": {"message": "Invalid API key"}}

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse())

    with pytest.raises(ModelResponseError, match="Anthropic API Error: Invalid API key"):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_stream_success(monkeypatch):
    client = AnthropicClient(model="claude-3-haiku", api_key="k")

    stream_chunks = [
        b'data: {"type": "content_block_delta", "delta": {"text": "Hello "}}',
        b'data: {"type": "content_block_delta", "delta": {"text": "world!"}}',
        b'data: {"type": "message_delta", "usage": {"output_tokens": 12}}',
        b'data: {"type": "message_stop", "stop_reason": "end_turn"}',
        b"data: [DONE]",
    ]

    class FakeStreamResponse:
        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield from stream_chunks

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeStreamResponse())

    tokens = []
    resp = client.generate([{"role": "user", "content": "hi"}], stream=True, on_token=tokens.append)

    assert resp.content == "Hello world!"
    assert resp.tokens_used == 12
    assert resp.finish_reason == "end_turn"
    assert tokens == ["Hello ", "world!"]


def test_generate_stream_connection_error_on_post(monkeypatch):
    client = AnthropicClient(model="claude-3-haiku", api_key="k")

    def fake_post(*args, **kwargs):
        raise RequestException("Connection dropped")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(ModelConnectionError, match="Could not reach Anthropic"):
        client.generate([{"role": "user", "content": "hi"}], stream=True)


def test_generate_stream_malformed_chunk(monkeypatch):
    client = AnthropicClient(model="claude-3-haiku", api_key="k")

    class FakeStreamResponse:
        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield b"data: {not-valid-json"

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeStreamResponse())

    with pytest.raises(ModelResponseError, match="Malformed stream chunk"):
        client.generate([{"role": "user", "content": "hi"}], stream=True)


def test_generate_stream_error_chunk(monkeypatch):
    client = AnthropicClient(model="claude-3-haiku", api_key="k")

    class FakeStreamResponse:
        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield b'data: {"type": "error", "error": {"message": "overloaded"}}'

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeStreamResponse())

    with pytest.raises(ModelResponseError, match="Anthropic API Error: overloaded"):
        client.generate([{"role": "user", "content": "hi"}], stream=True)


def test_generate_stream_dropped_mid_response(monkeypatch):
    client = AnthropicClient(model="claude-3-haiku", api_key="k")

    class FakeStreamResponse:
        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield b'data: {"type": "content_block_delta", "delta": {"text": "partial"}}'
            raise RequestException("mid-stream disconnect")

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeStreamResponse())

    with pytest.raises(ModelConnectionError, match="dropped mid-response"):
        client.generate([{"role": "user", "content": "hi"}], stream=True)


def test_generate_stream_ended_without_finish_reason(monkeypatch):
    client = AnthropicClient(model="claude-3-haiku", api_key="k")

    class FakeStreamResponse:
        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield b'data: {"type": "content_block_delta", "delta": {"text": "partial"}}'

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeStreamResponse())

    with pytest.raises(ModelConnectionError, match="ended before completion"):
        client.generate([{"role": "user", "content": "hi"}], stream=True)
