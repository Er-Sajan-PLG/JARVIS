"""Unit tests for app/models/cohere_client.py."""

import pytest
import requests
from requests.exceptions import RequestException

from app.models.cohere_client import CohereClient
from app.models.exceptions import (
    ModelConnectionError,
    ModelResponseError,
)


def test_constructor_success():
    client = CohereClient(model="command-r-plus", api_key="test-cohere-key", role="chat")
    assert client.model_name == "command-r-plus"
    assert client.role == "chat"
    assert client._api_key == "test-cohere-key"


def test_constructor_missing_key():
    with pytest.raises(ValueError, match="Cohere requires an API key"):
        CohereClient(model="command-r", api_key="")


def test_constructor_default_role():
    client = CohereClient(model="command-r", api_key="k")
    assert client.role == "general"


def test_generate_sync_success(monkeypatch):
    client = CohereClient(model="command-r", api_key="k")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"text": "Hello from Cohere!"}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    resp = client.generate(
        [
            {"role": "system", "content": "ignored system prompt"},
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"},
            {"role": "user", "content": "new question"},
        ],
        stream=False,
        temperature=0.3,
        max_tokens=250,
    )

    assert resp.content == "Hello from Cohere!"
    assert resp.model == "command-r"
    assert resp.finish_reason == "stop"
    assert captured["url"] == "https://api.cohere.ai/v1/chat"
    assert captured["headers"]["Authorization"] == "Bearer k"
    assert captured["json"]["model"] == "command-r"
    assert captured["json"]["message"] == "new question"
    assert captured["json"]["chat_history"] == [
        {"role": "USER", "message": "previous question"},
        {"role": "CHATBOT", "message": "previous answer"},
    ]
    assert captured["json"]["temperature"] == 0.3
    assert captured["json"]["max_tokens"] == 250
    assert captured["json"]["stream"] is False


def test_generate_sync_connection_error(monkeypatch):
    client = CohereClient(model="command-r", api_key="k")

    def fake_post(*args, **kwargs):
        raise RequestException("Network down")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(ModelConnectionError, match="Network down"):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_sync_malformed_response(monkeypatch):
    client = CohereClient(model="command-r", api_key="k")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse())

    with pytest.raises(ModelResponseError, match="Malformed response from Cohere"):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_stream_success(monkeypatch):
    client = CohereClient(model="command-r", api_key="k")

    lines = [
        b'{"event_type": "text-generation", "text": "Hello "}',
        b'{"event_type": "text-generation", "text": "Cohere!"}',
        b'{"event_type": "stream-end"}',
        b"invalid-json-line-should-be-ignored",
        b"",
    ]

    class FakeStreamResponse:
        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield from lines

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeStreamResponse())

    tokens = []
    resp = client.generate([{"role": "user", "content": "hi"}], stream=True, on_token=tokens.append)

    assert resp.content == "Hello Cohere!"
    assert resp.model == "command-r"
    assert resp.finish_reason == "stop"
    assert tokens == ["Hello ", "Cohere!"]


def test_generate_stream_connection_error(monkeypatch):
    client = CohereClient(model="command-r", api_key="k")

    def fake_post(*args, **kwargs):
        raise RequestException("Connection dropped")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(ModelConnectionError, match="Connection dropped"):
        client.generate([{"role": "user", "content": "hi"}], stream=True)
