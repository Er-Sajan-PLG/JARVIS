"""Unit tests for app/models/cloudflare_ai_client.py."""

from unittest.mock import MagicMock

import httpx
import pytest
from openai import APITimeoutError

from app.models.cloudflare_ai_client import CloudflareAIClient
from app.models.exceptions import (
    ModelConnectionError,
    ModelResponseError,
    ModelTimeoutError,
)


def test_constructor_success(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc-12345")
    client = CloudflareAIClient(
        model="@cf/meta/llama-3-8b-instruct",
        api_key="cf-token",
        role="worker",
    )
    assert client.model_name == "@cf/meta/llama-3-8b-instruct"
    assert client.role == "worker"
    assert "https://api.cloudflare.com/client/v4/accounts/acc-12345/ai" in str(
        client._client.base_url
    )


def test_constructor_missing_api_key(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc-12345")
    with pytest.raises(ValueError, match="Cloudflare Workers AI requires an API token"):
        CloudflareAIClient(model="m", api_key="")


def test_constructor_missing_account_id(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    with pytest.raises(ValueError, match="Cloudflare Workers AI requires an account ID"):
        CloudflareAIClient(model="m", api_key="k")


def test_constructor_default_role(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc-12345")
    client = CloudflareAIClient(model="m", api_key="k")
    assert client.role == "general"


def test_generate_sync_success(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc-12345")
    client = CloudflareAIClient(model="m", api_key="k")

    mock_choice = MagicMock()
    mock_choice.message.content = "cloudflare ai output"
    mock_choice.finish_reason = "stop"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.total_tokens = 22

    client._client.chat.completions.create = MagicMock(return_value=mock_response)

    resp = client.generate([{"role": "user", "content": "hi"}], stream=False)

    assert resp.content == "cloudflare ai output"
    assert resp.model == "m"
    assert resp.tokens_used == 22
    assert resp.finish_reason == "stop"


def test_generate_sync_empty_content_and_no_usage(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc-12345")
    client = CloudflareAIClient(model="m", api_key="k")

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


def test_generate_sync_openai_error(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc-12345")
    client = CloudflareAIClient(model="m", api_key="k")
    dummy_req = httpx.Request("POST", "https://api.cloudflare.com")
    client._client.chat.completions.create = MagicMock(side_effect=APITimeoutError(dummy_req))

    with pytest.raises(ModelTimeoutError):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_sync_shape_error(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc-12345")
    client = CloudflareAIClient(model="m", api_key="k")
    mock_response = MagicMock()
    mock_response.choices = []

    client._client.chat.completions.create = MagicMock(return_value=mock_response)

    with pytest.raises(ModelResponseError, match="Malformed response from model 'm'"):
        client.generate([{"role": "user", "content": "hi"}], stream=False)


def test_generate_stream_success(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc-12345")
    client = CloudflareAIClient(model="m", api_key="k")

    chunk_empty = MagicMock()
    chunk_empty.choices = []

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.content = "cloud"
    chunk1.choices[0].finish_reason = None

    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta.content = "flare"
    chunk2.choices[0].finish_reason = "stop"

    client._client.chat.completions.create = MagicMock(return_value=[chunk_empty, chunk1, chunk2])

    tokens = []
    resp = client.generate([{"role": "user", "content": "hi"}], stream=True, on_token=tokens.append)

    assert resp.content == "cloudflare"
    assert resp.model == "m"
    assert resp.finish_reason == "stop"
    assert tokens == ["cloud", "flare"]


def test_generate_stream_ended_without_finish_reason(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc-12345")
    client = CloudflareAIClient(model="m", api_key="k")

    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = "partial"
    chunk.choices[0].finish_reason = None

    client._client.chat.completions.create = MagicMock(return_value=[chunk])

    with pytest.raises(ModelConnectionError, match="ended before completion"):
        client.generate([{"role": "user", "content": "hi"}], stream=True)
