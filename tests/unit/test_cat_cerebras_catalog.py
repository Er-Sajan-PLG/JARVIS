"""Unit tests for app/utils/cerebras_catalog.py."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

import app.utils.cerebras_catalog as cc
from app.utils.cerebras_catalog import (
    CATALOG_URL,
    fetch_cerebras_models,
    is_free_model,
    search_cerebras_models,
)


@pytest.fixture(autouse=True)
def reset_cerebras_cache():
    """Reset cache before and after each test."""
    with cc._cache_lock:
        cc._cache["data"] = None
        cc._cache["fetched_at"] = 0.0
    yield
    with cc._cache_lock:
        cc._cache["data"] = None
        cc._cache["fetched_at"] = 0.0


def test_fetch_cerebras_models_success():
    raw_data = {
        "data": [
            {
                "id": "llama3.1-8b",
                "name": "Llama 3.1 8B",
                "description": "  Ultra-fast Cerebras model  ",
                "context_length": 8192,
                "pricing": {"prompt": "0.10", "completion": "0.10"},
            },
            {
                "id": "llama3.1-70b",
                "name": "",
                "description": None,
                "context_length": None,
                "pricing": None,
            },
            {
                "id": "",
                "name": "No ID",
            },
        ]
    }
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_cerebras_models(force=True)

        mock_get.assert_called_once_with(CATALOG_URL, timeout=10)
        assert len(models) == 2
        assert models[0]["id"] == "llama3.1-8b"
        assert models[0]["name"] == "Llama 3.1 8B"
        assert models[0]["description"] == "Ultra-fast Cerebras model"
        assert models[0]["context_length"] == 8192
        assert models[0]["pricing"] == {"prompt": "0.10", "completion": "0.10"}

        # Fallbacks for empty name/none fields
        assert models[1]["id"] == "llama3.1-70b"
        assert models[1]["name"] == "llama3.1-70b"
        assert models[1]["description"] == ""
        assert models[1]["context_length"] == 0
        assert models[1]["pricing"] == {}


def test_fetch_cerebras_models_caching():
    raw_data = {"data": [{"id": "cerebras-1", "name": "Cerebras 1"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        res1 = fetch_cerebras_models(force=False)
        res2 = fetch_cerebras_models(force=False)

        assert mock_get.call_count == 1
        assert res1 == res2


def test_fetch_cerebras_models_force_refresh():
    raw_data = {"data": [{"id": "cerebras-fresh", "name": "Fresh"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        with cc._cache_lock:
            cc._cache["data"] = [{"id": "cached"}]
            cc._cache["fetched_at"] = time.time()

        res = fetch_cerebras_models(force=True)
        assert mock_get.call_count == 1
        assert len(res) == 1
        assert res[0]["id"] == "cerebras-fresh"


def test_fetch_cerebras_models_network_failure_returns_empty_list():
    with patch("requests.get", side_effect=Exception("Connection refused")):
        models = fetch_cerebras_models(force=True)
        assert models == []


def test_fetch_cerebras_models_network_failure_returns_stale_cache():
    stale_data = [{"id": "stale-cer", "name": "Stale Cerebras"}]
    with cc._cache_lock:
        cc._cache["data"] = stale_data
        cc._cache["fetched_at"] = time.time()

    with patch("requests.get", side_effect=Exception("Network error")):
        models = fetch_cerebras_models(force=True)
        assert models == stale_data


def test_is_free_model():
    assert is_free_model({"pricing": {"prompt": "0", "completion": "0"}}) is True
    assert is_free_model({"pricing": {"prompt": "0.0", "completion": "0.0"}}) is True
    assert is_free_model({"pricing": {"prompt": " 0 ", "completion": " 0.0 "}}) is True
    assert is_free_model({"pricing": {"prompt": "0.10", "completion": "0.10"}}) is False
    assert is_free_model({"pricing": {"prompt": "0", "completion": "0.05"}}) is False
    assert is_free_model({}) is False
    assert is_free_model({"pricing": {}}) is False
    assert is_free_model({"pricing": None}) is False


def test_search_cerebras_models_default_args():
    sample_models = [
        {"id": "llama3.1-8b", "name": "Llama 3.1 8B", "context_length": 8192, "pricing": {}},
        {"id": "llama3.1-70b", "name": "Llama 3.1 70B", "context_length": 131072, "pricing": {}},
    ]
    with patch("app.utils.cerebras_catalog.fetch_cerebras_models", return_value=sample_models):
        results = search_cerebras_models(query="")
        assert len(results) == 2
        # Descending by context_length
        assert results[0]["id"] == "llama3.1-70b"
        assert results[1]["id"] == "llama3.1-8b"


def test_search_cerebras_models_query_filtering():
    sample_models = [
        {"id": "llama3.1-8b", "name": "Llama 3.1 8B", "context_length": 8192, "pricing": {}},
        {"id": "llama3.3-70b", "name": "Llama 3.3 70B", "context_length": 131072, "pricing": {}},
    ]
    with patch("app.utils.cerebras_catalog.fetch_cerebras_models", return_value=sample_models):
        # Query id
        res_id = search_cerebras_models("3.3")
        assert len(res_id) == 1
        assert res_id[0]["id"] == "llama3.3-70b"

        # Query name
        res_name = search_cerebras_models("8b")
        assert len(res_name) == 1
        assert res_name[0]["id"] == "llama3.1-8b"

        # Case-insensitive
        res_case = search_cerebras_models("LLAMA")
        assert len(res_case) == 2


def test_search_cerebras_models_free_only_filtering():
    sample_models = [
        {
            "id": "cer-free",
            "name": "Cerebras Free",
            "context_length": 8192,
            "pricing": {"prompt": "0", "completion": "0"},
        },
        {
            "id": "cer-paid",
            "name": "Cerebras Paid",
            "context_length": 8192,
            "pricing": {"prompt": "0.1", "completion": "0.2"},
        },
    ]
    with patch("app.utils.cerebras_catalog.fetch_cerebras_models", return_value=sample_models):
        free_res = search_cerebras_models(query="", free_only=True)
        assert len(free_res) == 1
        assert free_res[0]["id"] == "cer-free"

        all_res = search_cerebras_models(query="", free_only=False)
        assert len(all_res) == 2


def test_search_cerebras_models_limit_truncation():
    sample_models = [
        {"id": f"cer-{i}", "name": f"Cerebras {i}", "context_length": 1000 * i, "pricing": {}}
        for i in range(8)
    ]
    with patch("app.utils.cerebras_catalog.fetch_cerebras_models", return_value=sample_models):
        results = search_cerebras_models(query="", limit=3)
        assert len(results) == 3


def test_search_cerebras_models_network_failure_path():
    with patch("requests.get", side_effect=Exception("Timeout")):
        results = search_cerebras_models(query="")
        assert results == []
