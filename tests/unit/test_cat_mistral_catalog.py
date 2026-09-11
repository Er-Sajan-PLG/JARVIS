"""Unit tests for app/utils/mistral_catalog.py."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

import app.utils.mistral_catalog as mc
from app.utils.mistral_catalog import (
    CATALOG_URL,
    fetch_mistral_models,
    search_mistral_models,
)


@pytest.fixture(autouse=True)
def reset_mistral_cache():
    """Reset cache before and after each test."""
    with mc._cache_lock:
        mc._cache["data"] = None
        mc._cache["fetched_at"] = 0.0
    yield
    with mc._cache_lock:
        mc._cache["data"] = None
        mc._cache["fetched_at"] = 0.0


def test_fetch_mistral_models_success():
    raw_data = {
        "data": [
            {"id": "mistral-large-latest", "description": "Flagship model"},
            {"id": "mistral-small-latest"},
            {"id": ""},
            {"missing_id": True},
        ]
    }
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_mistral_models(api_key="dev-test-key-mistral", force=True)

        mock_get.assert_called_once_with(
            CATALOG_URL,
            headers={"Authorization": "Bearer dev-test-key-mistral"},
            timeout=10,
        )
        assert len(models) == 2
        assert models[0]["id"] == "mistral-large-latest"
        assert models[0]["name"] == "mistral-large-latest"
        assert models[0]["description"] == ""
        assert models[0]["context_length"] == 0
        assert models[0]["pricing"] == {}
        assert models[1]["id"] == "mistral-small-latest"


def test_fetch_mistral_models_without_api_key():
    raw_data = {"data": [{"id": "codestral-latest"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_mistral_models(api_key="", force=True)

        mock_get.assert_called_once_with(CATALOG_URL, headers={}, timeout=10)
        assert len(models) == 1
        assert models[0]["id"] == "codestral-latest"


def test_fetch_mistral_models_caching():
    raw_data = {"data": [{"id": "model-1"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        res1 = fetch_mistral_models()
        res2 = fetch_mistral_models()

        assert mock_get.call_count == 1
        assert res1 == res2


def test_fetch_mistral_models_force_refresh():
    raw_data = {"data": [{"id": "fresh-mistral"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        with mc._cache_lock:
            mc._cache["data"] = [{"id": "cached"}]
            mc._cache["fetched_at"] = time.time()

        res = fetch_mistral_models(force=True)
        assert mock_get.call_count == 1
        assert res[0]["id"] == "fresh-mistral"


def test_fetch_mistral_models_network_failure_returns_empty_list():
    with patch("requests.get", side_effect=Exception("Mistral service down")):
        models = fetch_mistral_models(force=True)
        assert models == []


def test_fetch_mistral_models_network_failure_returns_stale_cache():
    stale_data = [{"id": "stale-mistral", "name": "stale-mistral"}]
    with mc._cache_lock:
        mc._cache["data"] = stale_data
        mc._cache["fetched_at"] = time.time()

    with patch("requests.get", side_effect=Exception("Mistral service down")):
        models = fetch_mistral_models(force=True)
        assert models == stale_data


def test_search_mistral_models_default_args():
    sample_models = [
        {"id": "mistral-large", "name": "mistral-large", "pricing": {}},
        {"id": "mistral-small", "name": "mistral-small", "pricing": {}},
    ]
    with patch("app.utils.mistral_catalog.fetch_mistral_models", return_value=sample_models):
        res = search_mistral_models(query="")
        assert len(res) == 2


def test_search_mistral_models_query_filtering():
    sample_models = [
        {"id": "mistral-large", "name": "mistral-large", "pricing": {}},
        {"id": "open-mixtral-8x22b", "name": "open-mixtral-8x22b", "pricing": {}},
    ]
    with patch("app.utils.mistral_catalog.fetch_mistral_models", return_value=sample_models):
        res_id = search_mistral_models("mixtral")
        assert len(res_id) == 1
        assert res_id[0]["id"] == "open-mixtral-8x22b"

        res_case = search_mistral_models("LARGE")
        assert len(res_case) == 1
        assert res_case[0]["id"] == "mistral-large"


def test_search_mistral_models_free_only_filtering():
    sample_models = [
        {"id": "free-mistral", "name": "free-mistral", "pricing": {"prompt": "0"}},
        {"id": "paid-mistral", "name": "paid-mistral", "pricing": {"prompt": "0.2"}},
    ]
    with patch("app.utils.mistral_catalog.fetch_mistral_models", return_value=sample_models):
        models = search_mistral_models("")
        free_models = [m for m in models if m.get("pricing", {}).get("prompt") == "0"]
        assert len(free_models) == 1
        assert free_models[0]["id"] == "free-mistral"


def test_search_mistral_models_limit_truncation():
    sample_models = [{"id": f"model-{i}", "name": f"model-{i}", "pricing": {}} for i in range(10)]
    with patch("app.utils.mistral_catalog.fetch_mistral_models", return_value=sample_models):
        res = search_mistral_models(query="", limit=4)
        assert len(res) == 4


def test_search_mistral_models_network_failure_path():
    with patch("requests.get", side_effect=Exception("Timeout")):
        res = search_mistral_models(query="")
        assert res == []
