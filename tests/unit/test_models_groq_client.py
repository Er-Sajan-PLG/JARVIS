"""Unit tests for app/models/groq_client.py."""

from unittest.mock import MagicMock

import httpx
import pytest
from openai import APITimeoutError

from app.models.exceptions import (
    ModelConnectionError,
    ModelResponseError,
    ModelTimeoutError,
)
from app.models.groq_client import GroqClient


def test_constructor_success():
    client = GroqClient(
        model="llama-3.1-70b-versatile",
        api_key="g-key-123",
        role="expert",
    )
    assert client.model_name == "llama-3.1-70b-versatile"
    assert client.role == "expert"
    assert str(client._client.base_url) == "https://api.groq.com/openai/v1/"


def test_constructor_missing_key():
    with pytest.raises(ValueError, match="Groq requires an API key"):
        GroqClient(model="m", api_key="")


def test_constructor_default_role():
    client = GroqClient(model="m", api_key="k")
    assert client.role == "general"


def test_generate_sync_success():
    client = GroqClient(model="m", api_key="k")

    mock_choice = MagicMock()
    mock_choice.message.content = "groq response"
    mock_choice.finish_reason = "stop"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.total_tokens = 40

    client._client.chat.completions.create = MagicMock(return_value=mock_response)

    resp = client.generate([{"role": "user", "content": "hi"}], stream=False)

    assert resp.content == "groq response"
    assert resp.model == "m"
    assert resp.tokens_used == 40
    assert resp.finish_reason == "stop"


def test_generate_sync_empty_content_and_no_usage():
    client = GroqClient(model="m", api_key="k")

    mock_choice = MagicMock()
    mock_choice.message.content = None
    mock_choice.finish_reason = "stop"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = None

    client._client.chat.completions.create = MagicMock(return_value=mock_response)

    resp = client.generate([{"role": "user", "content": "hi"}], stream=False)
    assert resp.content == ""
    assert resp.tokens_used is None


def test_generate_sync_openai_error():
    client = GroqClient(model="m", api_key="k")
    dummy_req = httpx.Request("POST", "https://api.groq.com/openai/v1")
    client._client.chat.completions.create = MagicMock(side_effect=APITimeoutError(dummy_req))

    with pytest.raises(ModelTimeoutError):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_sync_shape_error():
    client = GroqClient(model="m", api_key="k")
    mock_response = MagicMock()
    mock_response.choices = []

    client._client.chat.completions.create = MagicMock(return_value=mock_response)

    with pytest.raises(ModelResponseError, match="Malformed response from model 'm'"):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_stream_success():
    client = GroqClient(model="m", api_key="k")

    chunk_empty = MagicMock()
    chunk_empty.choices = []

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.content = "Gro"
    chunk1.choices[0].finish_reason = None

    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta.content = "q"
    chunk2.choices[0].finish_reason = "stop"

    client._client.chat.completions.create = MagicMock(return_value=[chunk_empty, chunk1, chunk2])

    tokens = []
    resp = client.generate([{"role": "user", "content": "hi"}], stream=True, on_token=tokens.append)

    assert resp.content == "Groq"
    assert resp.model == "m"
    assert resp.finish_reason == "stop"
    assert tokens == ["Gro", "q"]


def test_generate_stream_ended_without_finish_reason():
    client = GroqClient(model="m", api_key="k")

    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = "partial"
    chunk.choices[0].finish_reason = None

    client._client.chat.completions.create = MagicMock(return_value=[chunk])

    with pytest.raises(ModelConnectionError, match="ended before completion"):
        client.generate([{"role": "user", "content": "hi"}], stream=True)
