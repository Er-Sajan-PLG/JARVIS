"""Unit tests for app/utils/together_catalog.py."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

import app.utils.together_catalog as tc
from app.utils.together_catalog import (
    CATALOG_URL,
    fetch_together_models,
    is_free_model,
    search_together_models,
)


@pytest.fixture(autouse=True)
def reset_together_cache():
    """Reset module cache before each test."""
    with tc._cache_lock:
        tc._cache["data"] = None
        tc._cache["fetched_at"] = 0.0
    yield
    with tc._cache_lock:
        tc._cache["data"] = None
        tc._cache["fetched_at"] = 0.0


def test_fetch_together_models_success():
    raw_data = {
        "data": [
            {
                "id": "togethercomputer/llama-2-7b",
                "name": "Llama 2 7B",
                "description": "  A 7B parameter open-weight model  ",
                "context_length": 4096,
                "pricing": {"prompt": "0.0002", "completion": "0.0002"},
            },
            {
                "id": "togethercomputer/no-name-model",
                "name": "",
                "description": None,
                "context_length": None,
                "pricing": None,
            },
            {
                "id": "",
                "name": "Empty ID Model",
            },
        ]
    }
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_together_models(force=True)

        mock_get.assert_called_once_with(CATALOG_URL, timeout=10)
        assert len(models) == 2
        assert models[0]["id"] == "togethercomputer/llama-2-7b"
        assert models[0]["name"] == "Llama 2 7B"
        assert models[0]["description"] == "A 7B parameter open-weight model"
        assert models[0]["context_length"] == 4096
        assert models[0]["pricing"] == {"prompt": "0.0002", "completion": "0.0002"}

        assert models[1]["id"] == "togethercomputer/no-name-model"
        assert models[1]["name"] == "togethercomputer/no-name-model"
        assert models[1]["description"] == ""
        assert models[1]["context_length"] == 0
        assert models[1]["pricing"] == {}


def test_fetch_together_models_caching():
    raw_data = {"data": [{"id": "model-1", "name": "Model 1", "context_length": 1000}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        res1 = fetch_together_models(force=False)
        res2 = fetch_together_models(force=False)

        assert mock_get.call_count == 1
        assert res1 == res2


def test_fetch_together_models_force_refresh():
    raw_data = {"data": [{"id": "model-1", "name": "Model 1"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        with tc._cache_lock:
            tc._cache["data"] = [{"id": "cached"}]
            tc._cache["fetched_at"] = time.time()

        res = fetch_together_models(force=True)
        assert mock_get.call_count == 1
        assert len(res) == 1
        assert res[0]["id"] == "model-1"


def test_fetch_together_models_network_failure_returns_empty_list():
    with patch("requests.get", side_effect=Exception("Connection refused")):
        models = fetch_together_models(force=True)
        assert models == []


def test_fetch_together_models_network_failure_returns_stale_cache():
    stale_data = [{"id": "stale-model", "name": "Stale"}]
    with tc._cache_lock:
        tc._cache["data"] = stale_data
        tc._cache["fetched_at"] = time.time()

    with patch("requests.get", side_effect=Exception("Network error")):
        models = fetch_together_models(force=True)
        assert models == stale_data


def test_is_free_model():
    assert is_free_model({"pricing": {"prompt": "0", "completion": "0"}}) is True
    assert is_free_model({"pricing": {"prompt": "0.0", "completion": "0.0"}}) is True
    assert is_free_model({"pricing": {"prompt": " 0 ", "completion": " 0.0 "}}) is True
    assert is_free_model({"pricing": {"prompt": "0.01", "completion": "0.0"}}) is False
    assert is_free_model({"pricing": {"prompt": "0.0", "completion": "0.02"}}) is False
    assert is_free_model({"pricing": {}}) is False
    assert is_free_model({}) is False
    assert is_free_model({"pricing": None}) is False


def test_search_together_models_default_args():
    sample_models = [
        {"id": "meta/llama-3-8b", "name": "Llama 3 8B", "context_length": 8192, "pricing": {}},
        {"id": "mistral/mistral-7b", "name": "Mistral 7B", "context_length": 32768, "pricing": {}},
    ]
    with patch("app.utils.together_catalog.fetch_together_models", return_value=sample_models):
        results = search_together_models(query="")
        assert len(results) == 2
        assert results[0]["id"] == "mistral/mistral-7b"
        assert results[1]["id"] == "meta/llama-3-8b"


def test_search_together_models_query_filtering():
    sample_models = [
        {"id": "meta/llama-3-8b", "name": "Llama 3 8B", "context_length": 8192, "pricing": {}},
        {"id": "mistral/mistral-7b", "name": "Mistral 7B", "context_length": 32768, "pricing": {}},
        {"id": "qwen/qwen-2.5", "name": "Qwen 2.5", "context_length": 16384, "pricing": {}},
    ]
    with patch("app.utils.together_catalog.fetch_together_models", return_value=sample_models):
        res_id = search_together_models("meta/")
        assert len(res_id) == 1
        assert res_id[0]["id"] == "meta/llama-3-8b"

        res_name = search_together_models("Mistral")
        assert len(res_name) == 1
        assert res_name[0]["id"] == "mistral/mistral-7b"

        res_case = search_together_models("QWEN")
        assert len(res_case) == 1
        assert res_case[0]["id"] == "qwen/qwen-2.5"


def test_search_together_models_free_only_filtering():
    sample_models = [
        {
            "id": "free-1",
            "name": "Free 1",
            "context_length": 4096,
            "pricing": {"prompt": "0", "completion": "0"},
        },
        {
            "id": "paid-1",
            "name": "Paid 1",
            "context_length": 8192,
            "pricing": {"prompt": "0.1", "completion": "0.2"},
        },
    ]
    with patch("app.utils.together_catalog.fetch_together_models", return_value=sample_models):
        free_res = search_together_models(query="", free_only=True)
        assert len(free_res) == 1
        assert free_res[0]["id"] == "free-1"

        all_res = search_together_models(query="", free_only=False)
        assert len(all_res) == 2


def test_search_together_models_limit_truncation():
    sample_models = [
        {"id": f"model-{i}", "name": f"Model {i}", "context_length": i * 1000, "pricing": {}}
        for i in range(10)
    ]
    with patch("app.utils.together_catalog.fetch_together_models", return_value=sample_models):
        limited = search_together_models(query="", limit=3)
        assert len(limited) == 3


def test_search_together_models_network_failure_path():
    with patch("requests.get", side_effect=Exception("Timeout")):
        results = search_together_models(query="")
        assert results == []
