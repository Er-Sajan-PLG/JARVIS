"""Unit tests for app/models/mistral_client.py."""

from unittest.mock import MagicMock

import httpx
import pytest
from openai import APITimeoutError

from app.models.exceptions import (
    ModelConnectionError,
    ModelResponseError,
    ModelTimeoutError,
)
from app.models.mistral_client import MistralClient


def test_constructor_success():
    client = MistralClient(
        model="mistral-large-latest",
        api_key="m-key-123",
        role="general",
    )
    assert client.model_name == "mistral-large-latest"
    assert client.role == "general"
    assert str(client._client.base_url) == "https://api.mistral.ai/v1/"


def test_constructor_missing_key():
    with pytest.raises(ValueError, match="Mistral AI requires an API key"):
        MistralClient(model="m", api_key="")


def test_constructor_default_role():
    client = MistralClient(model="m", api_key="k")
    assert client.role == "general"


def test_generate_sync_success():
    client = MistralClient(model="m", api_key="k")

    mock_choice = MagicMock()
    mock_choice.message.content = "mistral response"
    mock_choice.finish_reason = "stop"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.total_tokens = 33

    client._client.chat.completions.create = MagicMock(return_value=mock_response)

    resp = client.generate([{"role": "user", "content": "hi"}], stream=False)

    assert resp.content == "mistral response"
    assert resp.model == "m"
    assert resp.tokens_used == 33
    assert resp.finish_reason == "stop"


def test_generate_sync_empty_content_and_no_usage():
    client = MistralClient(model="m", api_key="k")

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
    client = MistralClient(model="m", api_key="k")
    dummy_req = httpx.Request("POST", "https://api.mistral.ai/v1")
    client._client.chat.completions.create = MagicMock(side_effect=APITimeoutError(dummy_req))

    with pytest.raises(ModelTimeoutError):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_sync_shape_error():
    client = MistralClient(model="m", api_key="k")
    mock_response = MagicMock()
    mock_response.choices = []

    client._client.chat.completions.create = MagicMock(return_value=mock_response)

    with pytest.raises(ModelResponseError, match="Malformed response from model 'm'"):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_stream_success():
    client = MistralClient(model="m", api_key="k")

    chunk_empty = MagicMock()
    chunk_empty.choices = []

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.content = "Mis"
    chunk1.choices[0].finish_reason = None

    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta.content = "tral"
    chunk2.choices[0].finish_reason = "stop"

    client._client.chat.completions.create = MagicMock(return_value=[chunk_empty, chunk1, chunk2])

    tokens = []
    resp = client.generate([{"role": "user", "content": "hi"}], stream=True, on_token=tokens.append)

    assert resp.content == "Mistral"
    assert resp.model == "m"
    assert resp.finish_reason == "stop"
    assert tokens == ["Mis", "tral"]


def test_generate_stream_ended_without_finish_reason():
    client = MistralClient(model="m", api_key="k")

    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = "partial"
    chunk.choices[0].finish_reason = None

    client._client.chat.completions.create = MagicMock(return_value=[chunk])

    with pytest.raises(ModelConnectionError, match="ended before completion"):
        client.generate([{"role": "user", "content": "hi"}], stream=True)
