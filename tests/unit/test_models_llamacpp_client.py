"""Unit tests for app/models/llamacpp_client.py."""

from unittest.mock import MagicMock

import httpx
import pytest
from openai import APITimeoutError

from app.models.exceptions import (
    ModelConnectionError,
    ModelResponseError,
    ModelTimeoutError,
)
from app.models.llamacpp_client import LlamaCppClient


def test_constructor_defaults(monkeypatch):
    monkeypatch.setattr("app.models.llamacpp_client.get_default_model", lambda: "default-model")
    client = LlamaCppClient()
    assert client.model_name == "default-model"
    assert client.role == "general"
    assert client._api_key == "not-needed"


def test_constructor_with_params():
    client = LlamaCppClient(
        model="custom-model", base_url="http://localhost:9999/v1", api_key="test-key", role="code"
    )
    assert client.model_name == "custom-model"
    assert client.role == "code"
    assert client._api_key == "test-key"


def test_constructor_resolves_env_key(monkeypatch):
    monkeypatch.setenv("LLAMA_KEY", "resolved-secret")
    client = LlamaCppClient(model="m", api_key="env:LLAMA_KEY")
    assert client._api_key == "resolved-secret"


def test_constructor_env_key_not_found_keeps_original():
    client = LlamaCppClient(model="m", api_key="env:MISSING_KEY_VAR")
    assert client._api_key == "env:MISSING_KEY_VAR"


def test_generate_sync_success():
    client = LlamaCppClient(model="m", api_key="k")

    mock_choice = MagicMock()
    mock_choice.message.content = "llama response"
    mock_choice.finish_reason = "stop"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.total_tokens = 42

    client._client.chat.completions.create = MagicMock(return_value=mock_response)

    resp = client.generate([{"role": "user", "content": "hi"}], stream=False, temperature=0.7)

    assert resp.content == "llama response"
    assert resp.model == "m"
    assert resp.tokens_used == 42
    assert resp.finish_reason == "stop"
    client._client.chat.completions.create.assert_called_once_with(
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.7,
    )


def test_generate_sync_no_usage():
    client = LlamaCppClient(model="m", api_key="k")

    mock_choice = MagicMock()
    mock_choice.message.content = "answer"
    mock_choice.finish_reason = "stop"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = None

    client._client.chat.completions.create = MagicMock(return_value=mock_response)

    resp = client.generate([{"role": "user", "content": "hi"}], stream=False)
    assert resp.tokens_used is None


def test_generate_sync_openai_error():
    client = LlamaCppClient(model="m", api_key="k")

    dummy_request = httpx.Request("POST", "http://localhost:8080/v1")
    client._client.chat.completions.create = MagicMock(side_effect=APITimeoutError(dummy_request))

    with pytest.raises(ModelTimeoutError):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_sync_shape_error():
    client = LlamaCppClient(model="m", api_key="k")

    mock_response = MagicMock()
    mock_response.choices = []  # will trigger IndexError on choices[0]

    client._client.chat.completions.create = MagicMock(return_value=mock_response)

    with pytest.raises(ModelResponseError, match="Malformed response from model 'm'"):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_stream_success():
    client = LlamaCppClient(model="m", api_key="k")

    chunk_empty = MagicMock()
    chunk_empty.choices = []

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.content = "tok1 "
    chunk1.choices[0].finish_reason = None

    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta.content = "tok2"
    chunk2.choices[0].finish_reason = "stop"

    client._client.chat.completions.create = MagicMock(return_value=[chunk_empty, chunk1, chunk2])

    tokens = []
    resp = client.generate([{"role": "user", "content": "hi"}], stream=True, on_token=tokens.append)

    assert resp.content == "tok1 tok2"
    assert resp.model == "m"
    assert resp.finish_reason == "stop"
    assert tokens == ["tok1 ", "tok2"]


def test_generate_stream_ended_without_finish_reason():
    client = LlamaCppClient(model="m", api_key="k")

    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = "partial"
    chunk.choices[0].finish_reason = None

    client._client.chat.completions.create = MagicMock(return_value=[chunk])

    with pytest.raises(ModelConnectionError, match="ended before completion"):
        client.generate([{"role": "user", "content": "hi"}], stream=True)
