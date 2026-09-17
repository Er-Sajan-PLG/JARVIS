"""Unit tests for app/utils/nvidia_nim_catalog.py."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

import app.utils.nvidia_nim_catalog as nnc
from app.utils.nvidia_nim_catalog import (
    CATALOG_URL,
    fetch_nvidia_models,
    search_nvidia_models,
)


@pytest.fixture(autouse=True)
def reset_nvidia_cache():
    """Reset cache before and after each test."""
    with nnc._cache_lock:
        nnc._cache["data"] = None
        nnc._cache["fetched_at"] = 0.0
    yield
    with nnc._cache_lock:
        nnc._cache["data"] = None
        nnc._cache["fetched_at"] = 0.0


def test_fetch_nvidia_models_success():
    raw_data = {
        "data": [
            {"id": "meta/llama-3.1-405b-instruct", "description": "405B flagship NIM"},
            {"id": "nvidia/nemotron-4-340b-instruct"},
            {"id": ""},
            {"other": "none"},
        ]
    }
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_nvidia_models(api_key="nv_key_123", force=True)

        mock_get.assert_called_once_with(
            CATALOG_URL,
            headers={"Authorization": "Bearer nv_key_123"},
            timeout=10,
        )
        assert len(models) == 2
        assert models[0]["id"] == "meta/llama-3.1-405b-instruct"
        assert models[0]["name"] == "meta/llama-3.1-405b-instruct"
        assert models[0]["description"] == "405B flagship NIM"
        assert models[0]["context_length"] == 0
        assert models[0]["pricing"] == {}
        assert models[1]["id"] == "nvidia/nemotron-4-340b-instruct"
        assert models[1]["description"] == ""


def test_fetch_nvidia_models_without_explicit_key_uses_env(monkeypatch):
    """An empty api_key falls back to NVIDIA_API_KEY from the environment."""
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-env-key")
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    raw_data = {"data": [{"id": "meta/llama-3.1-70b-instruct"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_nvidia_models(api_key="", force=True)

        mock_get.assert_called_once_with(
            CATALOG_URL, headers={"Authorization": "Bearer nvapi-env-key"}, timeout=10
        )
        assert len(models) == 1


def test_fetch_nvidia_models_without_any_key(monkeypatch):
    """With no key anywhere, the request goes out unauthenticated."""
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    raw_data = {"data": [{"id": "meta/llama-3.1-70b-instruct"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_nvidia_models(api_key="", force=True)

        mock_get.assert_called_once_with(CATALOG_URL, headers={}, timeout=10)
        assert len(models) == 1


def test_fetch_nvidia_models_caching():
    raw_data = {"data": [{"id": "nim-1"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        res1 = fetch_nvidia_models()
        res2 = fetch_nvidia_models()

        assert mock_get.call_count == 1
        assert res1 == res2


def test_fetch_nvidia_models_force_refresh():
    raw_data = {"data": [{"id": "fresh-nim"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        with nnc._cache_lock:
            nnc._cache["data"] = [{"id": "cached"}]
            nnc._cache["fetched_at"] = time.time()

        res = fetch_nvidia_models(force=True)
        assert mock_get.call_count == 1
        assert res[0]["id"] == "fresh-nim"


def test_fetch_nvidia_models_network_failure_returns_empty_list():
    with patch("requests.get", side_effect=Exception("NVIDIA NIM unreachable")):
        models = fetch_nvidia_models(force=True)
        assert models == []


def test_fetch_nvidia_models_network_failure_returns_stale_cache():
    stale_data = [{"id": "stale-nim", "name": "stale-nim"}]
    with nnc._cache_lock:
        nnc._cache["data"] = stale_data
        nnc._cache["fetched_at"] = time.time()

    with patch("requests.get", side_effect=Exception("NVIDIA NIM unreachable")):
        models = fetch_nvidia_models(force=True)
        assert models == stale_data


def test_search_nvidia_models_default_args():
    sample_models = [
        {"id": "meta/llama-3.1-8b", "name": "meta/llama-3.1-8b", "pricing": {}},
        {"id": "meta/llama-3.1-70b", "name": "meta/llama-3.1-70b", "pricing": {}},
    ]
    with patch("app.utils.nvidia_nim_catalog.fetch_nvidia_models", return_value=sample_models):
        res = search_nvidia_models(query="")
        assert len(res) == 2


def test_search_nvidia_models_query_filtering():
    sample_models = [
        {"id": "meta/llama-3.1-8b", "name": "meta/llama-3.1-8b", "pricing": {}},
        {"id": "nvidia/nemotron-4-340b", "name": "nvidia/nemotron-4-340b", "pricing": {}},
    ]
    with patch("app.utils.nvidia_nim_catalog.fetch_nvidia_models", return_value=sample_models):
        res_id = search_nvidia_models("nemotron")
        assert len(res_id) == 1
        assert res_id[0]["id"] == "nvidia/nemotron-4-340b"

        res_case = search_nvidia_models("LLAMA")
        assert len(res_case) == 1
        assert res_case[0]["id"] == "meta/llama-3.1-8b"


def test_search_nvidia_models_free_only_filtering():
    sample_models = [
        {"id": "free-nim", "name": "free-nim", "pricing": {"prompt": "0"}},
        {"id": "paid-nim", "name": "paid-nim", "pricing": {"prompt": "0.3"}},
    ]
    with patch("app.utils.nvidia_nim_catalog.fetch_nvidia_models", return_value=sample_models):
        models = search_nvidia_models("")
        free_models = [m for m in models if m.get("pricing", {}).get("prompt") == "0"]
        assert len(free_models) == 1
        assert free_models[0]["id"] == "free-nim"


def test_search_nvidia_models_limit_truncation():
    sample_models = [{"id": f"model-{i}", "name": f"model-{i}", "pricing": {}} for i in range(10)]
    with patch("app.utils.nvidia_nim_catalog.fetch_nvidia_models", return_value=sample_models):
        res = search_nvidia_models(query="", limit=3)
        assert len(res) == 3


def test_search_nvidia_models_network_failure_path():
    with patch("requests.get", side_effect=Exception("Timeout")):
        res = search_nvidia_models(query="")
        assert res == []
