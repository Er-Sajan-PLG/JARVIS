"""Unit tests for app/utils/hf_catalog.py."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

import app.utils.hf_catalog as hfc
from app.utils.hf_catalog import (
    API_URL,
    fetch_hf_models,
    search_hf_models,
)


@pytest.fixture(autouse=True)
def reset_hf_cache():
    """Reset cache before and after each test."""
    with hfc._cache_lock:
        hfc._cache["data"] = None
        hfc._cache["fetched_at"] = 0.0
    yield
    with hfc._cache_lock:
        hfc._cache["data"] = None
        hfc._cache["fetched_at"] = 0.0


def test_fetch_hf_models_success():
    # Include with slash, without slash, empty id, and over 50 items to test limit
    raw_data = [
        {"id": "meta-llama/Meta-Llama-3-8B"},
        {"id": "gpt2"},
        {"id": ""},
    ] + [{"id": f"org/model-{i}"} for i in range(60)]

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_hf_models(api_key="hf_token_abc", force=True)

        mock_get.assert_called_once_with(
            f"{API_URL}?filter=text-generation",
            headers={"Authorization": "Bearer hf_token_abc"},
            timeout=10,
        )
        assert len(models) == 50  # Capped at first 50
        assert models[0]["id"] == "meta-llama/Meta-Llama-3-8B"
        assert models[0]["name"] == "Meta-Llama-3-8B"
        assert models[1]["id"] == "gpt2"
        assert models[1]["name"] == "gpt2"


def test_fetch_hf_models_without_api_key():
    raw_data = [{"id": "google/flan-t5-base"}]
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_hf_models(api_key="", force=True)

        mock_get.assert_called_once_with(
            f"{API_URL}?filter=text-generation",
            headers={},
            timeout=10,
        )
        assert len(models) == 1
        assert models[0]["name"] == "flan-t5-base"


def test_fetch_hf_models_caching():
    raw_data = [{"id": "model-1"}]
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        res1 = fetch_hf_models()
        res2 = fetch_hf_models()

        assert mock_get.call_count == 1
        assert res1 == res2


def test_fetch_hf_models_force_refresh():
    raw_data = [{"id": "fresh-model"}]
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        with hfc._cache_lock:
            hfc._cache["data"] = [{"id": "cached"}]
            hfc._cache["fetched_at"] = time.time()

        res = fetch_hf_models(force=True)
        assert mock_get.call_count == 1
        assert res[0]["id"] == "fresh-model"


def test_fetch_hf_models_network_failure_returns_empty_list():
    with patch("requests.get", side_effect=Exception("HuggingFace down")):
        models = fetch_hf_models(force=True)
        assert models == []


def test_fetch_hf_models_network_failure_returns_stale_cache():
    stale_data = [{"id": "stale-hf", "name": "stale-hf"}]
    with hfc._cache_lock:
        hfc._cache["data"] = stale_data
        hfc._cache["fetched_at"] = time.time()

    with patch("requests.get", side_effect=Exception("HuggingFace down")):
        models = fetch_hf_models(force=True)
        assert models == stale_data


def test_search_hf_models_default_args():
    sample_models = [
        {"id": "meta-llama/Llama-3-8B", "name": "Llama-3-8B", "pricing": {}},
        {"id": "mistralai/Mistral-7B-v0.1", "name": "Mistral-7B-v0.1", "pricing": {}},
    ]
    with patch("app.utils.hf_catalog.fetch_hf_models", return_value=sample_models):
        res = search_hf_models(query="")
        assert len(res) == 2


def test_search_hf_models_query_filtering():
    sample_models = [
        {"id": "meta-llama/Llama-3-8B", "name": "Llama-3-8B", "pricing": {}},
        {"id": "mistralai/Mistral-7B-v0.1", "name": "Mistral-7B-v0.1", "pricing": {}},
    ]
    with patch("app.utils.hf_catalog.fetch_hf_models", return_value=sample_models):
        # By id
        res_id = search_hf_models("meta-llama")
        assert len(res_id) == 1
        assert res_id[0]["id"] == "meta-llama/Llama-3-8B"

        # By name
        res_name = search_hf_models("Mistral-7B")
        assert len(res_name) == 1
        assert res_name[0]["name"] == "Mistral-7B-v0.1"

        # Case-insensitive
        res_case = search_hf_models("LLAMA")
        assert len(res_case) == 1
        assert res_case[0]["id"] == "meta-llama/Llama-3-8B"


def test_search_hf_models_free_only_filtering():
    sample_models = [
        {"id": "hf-free", "name": "hf-free", "pricing": {"prompt": "0"}},
        {"id": "hf-paid", "name": "hf-paid", "pricing": {"prompt": "0.1"}},
    ]
    with patch("app.utils.hf_catalog.fetch_hf_models", return_value=sample_models):
        models = search_hf_models("")
        free_models = [m for m in models if m.get("pricing", {}).get("prompt") == "0"]
        assert len(free_models) == 1
        assert free_models[0]["id"] == "hf-free"


def test_search_hf_models_limit_truncation():
    sample_models = [{"id": f"hf-{i}", "name": f"hf-{i}", "pricing": {}} for i in range(10)]
    with patch("app.utils.hf_catalog.fetch_hf_models", return_value=sample_models):
        res = search_hf_models(query="", limit=3)
        assert len(res) == 3


def test_search_hf_models_network_failure_path():
    with patch("requests.get", side_effect=Exception("Timeout")):
        res = search_hf_models(query="")
        assert res == []
