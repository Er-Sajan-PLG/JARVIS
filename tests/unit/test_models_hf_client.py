"""Unit tests for app/models/hf_client.py."""

import pytest
import requests
from requests.exceptions import RequestException

from app.models.exceptions import (
    ModelConnectionError,
    ModelResponseError,
)
from app.models.hf_client import HuggingFaceClient


def test_constructor_success():
    client = HuggingFaceClient(model="google/flan-t5-large", api_key="hf-token-123", role="qa")
    assert client.model_name == "google/flan-t5-large"
    assert client.role == "qa"
    assert client._api_key == "hf-token-123"


def test_constructor_missing_key():
    with pytest.raises(ValueError, match="Hugging Face requires an API token"):
        HuggingFaceClient(model="google/flan-t5-large", api_key="")


def test_constructor_default_role():
    client = HuggingFaceClient(model="google/flan-t5-large", api_key="k")
    assert client.role == "general"


def test_generate_sync_success_list_dict(monkeypatch):
    client = HuggingFaceClient(model="gpt2", api_key="k")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return [{"generated_text": "Hello from HF!"}]

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    tokens = []
    resp = client.generate(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hey"},
        ],
        temperature=0.8,
        max_tokens=50,
        on_token=tokens.append,
    )

    assert resp.content == "Hello from HF!"
    assert resp.model == "gpt2"
    assert resp.finish_reason == "stop"
    assert tokens == ["Hello from HF!"]
    assert captured["url"] == "https://api-inference.huggingface.co/models/gpt2"
    assert captured["headers"]["Authorization"] == "Bearer k"
    assert "[SYSTEM]: You are helpful." in captured["json"]["inputs"]
    assert "[USER]: Hi" in captured["json"]["inputs"]
    assert "[ASSISTANT]: Hey" in captured["json"]["inputs"]
    assert captured["json"]["parameters"]["temperature"] == 0.8
    assert captured["json"]["parameters"]["max_new_tokens"] == 50


def test_generate_sync_success_list_string(monkeypatch):
    client = HuggingFaceClient(model="gpt2", api_key="k")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return ["plain text item"]

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse())

    resp = client.generate([{"role": "user", "content": "test"}])
    assert resp.content == "plain text item"


def test_generate_sync_success_dict(monkeypatch):
    client = HuggingFaceClient(model="gpt2", api_key="k")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"result": "ok"}

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse())

    resp = client.generate([{"role": "user", "content": "test"}])
    assert resp.content == "{'result': 'ok'}"


def test_generate_sync_connection_error(monkeypatch):
    client = HuggingFaceClient(model="gpt2", api_key="k")

    def fake_post(*args, **kwargs):
        raise RequestException("Inference API unreachable")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(ModelConnectionError, match="Inference API unreachable"):
        client.generate([{"role": "user", "content": "test"}])


def test_generate_sync_malformed_response(monkeypatch):
    client = HuggingFaceClient(model="gpt2", api_key="k")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            raise ValueError("not valid json")

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse())

    with pytest.raises(ModelResponseError, match="Malformed response from Hugging Face"):
        client.generate([{"role": "user", "content": "test"}])
