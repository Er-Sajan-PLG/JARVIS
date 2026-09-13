"""Unit tests for app/utils/cohere_catalog.py."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

import app.utils.cohere_catalog as coh
from app.utils.cohere_catalog import (
    CATALOG_URL,
    fetch_cohere_models,
    search_cohere_models,
)


@pytest.fixture(autouse=True)
def reset_cohere_cache():
    """Reset cache before and after each test."""
    with coh._cache_lock:
        coh._cache["data"] = None
        coh._cache["fetched_at"] = 0.0
    yield
    with coh._cache_lock:
        coh._cache["data"] = None
        coh._cache["fetched_at"] = 0.0


def test_fetch_cohere_models_success():
    raw_data = {
        "models": [
            {"name": "command-r-plus", "context_length": 128000},
            {"name": "command-light"},
            {"name": ""},
            {"other": "no-name"},
        ]
    }
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_cohere_models(api_key="test-cohere-key", force=True)

        mock_get.assert_called_once_with(
            CATALOG_URL,
            headers={"Authorization": "Bearer test-cohere-key"},
            timeout=10,
        )
        assert len(models) == 2
        assert models[0]["id"] == "command-r-plus"
        assert models[0]["name"] == "command-r-plus"
        assert models[0]["description"] == ""
        assert models[0]["context_length"] == 0
        assert models[0]["pricing"] == {}
        assert models[1]["id"] == "command-light"


def test_fetch_cohere_models_without_api_key():
    raw_data = {"models": [{"name": "command"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_cohere_models(api_key="", force=True)

        mock_get.assert_called_once_with(CATALOG_URL, headers={}, timeout=10)
        assert len(models) == 1


def test_fetch_cohere_models_caching():
    raw_data = {"models": [{"name": "command"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        res1 = fetch_cohere_models()
        res2 = fetch_cohere_models()

        assert mock_get.call_count == 1
        assert res1 == res2


def test_fetch_cohere_models_force_refresh():
    raw_data = {"models": [{"name": "command-new"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        with coh._cache_lock:
            coh._cache["data"] = [{"id": "cached"}]
            coh._cache["fetched_at"] = time.time()

        res = fetch_cohere_models(force=True)
        assert mock_get.call_count == 1
        assert res[0]["id"] == "command-new"


def test_fetch_cohere_models_network_failure_returns_empty_list():
    with patch("requests.get", side_effect=Exception("Connection reset")):
        models = fetch_cohere_models(force=True)
        assert models == []


def test_fetch_cohere_models_network_failure_returns_stale_cache():
    stale_data = [{"id": "stale-cohere", "name": "stale-cohere"}]
    with coh._cache_lock:
        coh._cache["data"] = stale_data
        coh._cache["fetched_at"] = time.time()

    with patch("requests.get", side_effect=Exception("Connection reset")):
        models = fetch_cohere_models(force=True)
        assert models == stale_data


def test_search_cohere_models_default_args():
    sample_models = [
        {"id": "command-r", "name": "command-r", "pricing": {}},
        {"id": "command-r-plus", "name": "command-r-plus", "pricing": {}},
    ]
    with patch("app.utils.cohere_catalog.fetch_cohere_models", return_value=sample_models):
        res = search_cohere_models(query="")
        assert len(res) == 2


def test_search_cohere_models_query_filtering():
    sample_models = [
        {"id": "command-r", "name": "command-r", "pricing": {}},
        {"id": "embed-english-v3.0", "name": "embed-english-v3.0", "pricing": {}},
    ]
    with patch("app.utils.cohere_catalog.fetch_cohere_models", return_value=sample_models):
        res_id = search_cohere_models("embed")
        assert len(res_id) == 1
        assert res_id[0]["id"] == "embed-english-v3.0"

        res_case = search_cohere_models("COMMAND")
        assert len(res_case) == 1
        assert res_case[0]["id"] == "command-r"


def test_search_cohere_models_free_only_filtering():
    # Cohere catalog entries do not have pricing set / free_only parameter
    sample_models = [
        {"id": "command-r", "name": "command-r", "pricing": {}},
        {"id": "command-r-plus", "name": "command-r-plus", "pricing": {"prompt": "0"}},
    ]
    with patch("app.utils.cohere_catalog.fetch_cohere_models", return_value=sample_models):
        models = search_cohere_models("")
        free_models = [m for m in models if m.get("pricing", {}).get("prompt") == "0"]
        assert len(free_models) == 1
        assert free_models[0]["id"] == "command-r-plus"


def test_search_cohere_models_limit_truncation():
    sample_models = [{"id": f"model-{i}", "name": f"model-{i}", "pricing": {}} for i in range(10)]
    with patch("app.utils.cohere_catalog.fetch_cohere_models", return_value=sample_models):
        res = search_cohere_models(query="", limit=4)
        assert len(res) == 4


def test_search_cohere_models_network_failure_path():
    with patch("requests.get", side_effect=Exception("Timeout")):
        res = search_cohere_models(query="")
        assert res == []
