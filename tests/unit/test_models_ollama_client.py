"""Unit tests for app/models/ollama_client.py."""

from unittest.mock import MagicMock

import httpx
import ollama
import pytest

from app.models.exceptions import (
    ModelConnectionError,
    ModelResponseError,
)
from app.models.ollama_client import OllamaClient


def test_constructor_defaults():
    client = OllamaClient(model="llama3")
    assert client.model_name == "llama3"
    assert client.role == "general"
    assert client._api_key == "not-needed"


def test_constructor_env_key(monkeypatch):
    monkeypatch.setenv("OLLAMA_KEY_VAR", "my-ollama-secret")
    client = OllamaClient(model="llama3", api_key="env:OLLAMA_KEY_VAR")
    assert client._api_key == "my-ollama-secret"


def test_constructor_empty_key_defaults_to_not_needed():
    client = OllamaClient(model="llama3", api_key="")
    assert client._api_key == "not-needed"


def test_constructor_strips_base_url_slash():
    client = OllamaClient(model="llama3", base_url="http://localhost:11434/")
    assert str(client._client.base_url) == "http://localhost:11434/v1/"


def test_generate_sync_success():
    client = OllamaClient(model="llama3")

    mock_choice = MagicMock()
    mock_choice.message.content = "ollama output"
    mock_choice.finish_reason = "stop"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.total_tokens = 55

    client._client.chat.completions.create = MagicMock(return_value=mock_response)

    resp = client.generate([{"role": "user", "content": "hi"}], stream=False)

    assert resp.content == "ollama output"
    assert resp.model == "llama3"
    assert resp.tokens_used == 55
    assert resp.finish_reason == "stop"


def test_generate_sync_ollama_response_error():
    client = OllamaClient(model="llama3")

    resp_err = ollama.ResponseError("model not found", status_code=404)
    client._client.chat.completions.create = MagicMock(side_effect=resp_err)

    with pytest.raises(ModelResponseError, match="HTTP 404"):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_sync_httpx_connection_error():
    client = OllamaClient(model="llama3")

    conn_err = httpx.ConnectError("Connection refused")
    client._client.chat.completions.create = MagicMock(side_effect=conn_err)

    with pytest.raises(ModelConnectionError, match="Could not connect to Ollama"):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_sync_shape_error():
    client = OllamaClient(model="llama3")

    mock_response = MagicMock()
    mock_response.choices = []

    client._client.chat.completions.create = MagicMock(return_value=mock_response)

    with pytest.raises(ModelResponseError, match="Malformed response from Ollama"):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_stream_success():
    client = OllamaClient(model="llama3")

    chunk_empty = MagicMock()
    chunk_empty.choices = []

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.content = "token1 "
    chunk1.choices[0].finish_reason = None

    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta.content = "token2"
    chunk2.choices[0].finish_reason = "stop"

    client._client.chat.completions.create = MagicMock(return_value=[chunk_empty, chunk1, chunk2])

    tokens = []
    resp = client.generate([{"role": "user", "content": "hi"}], stream=True, on_token=tokens.append)

    assert resp.content == "token1 token2"
    assert resp.model == "llama3"
    assert resp.finish_reason == "stop"
    assert tokens == ["token1 ", "token2"]


def test_generate_stream_ended_without_finish_reason():
    client = OllamaClient(model="llama3")

    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = "token1"
    chunk.choices[0].finish_reason = None

    client._client.chat.completions.create = MagicMock(return_value=[chunk])

    with pytest.raises(ModelConnectionError, match="ended before completion"):
        client.generate([{"role": "user", "content": "hi"}], stream=True)
