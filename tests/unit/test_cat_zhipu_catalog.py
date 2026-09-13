"""Unit tests for app/utils/zhipu_catalog.py."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

import app.utils.zhipu_catalog as zc
from app.utils.zhipu_catalog import (
    CATALOG_URL,
    fetch_zhipu_models,
    search_zhipu_models,
)


@pytest.fixture(autouse=True)
def reset_zhipu_cache():
    """Reset cache before and after each test."""
    with zc._cache_lock:
        zc._cache["data"] = None
        zc._cache["fetched_at"] = 0.0
    yield
    with zc._cache_lock:
        zc._cache["data"] = None
        zc._cache["fetched_at"] = 0.0


def test_fetch_zhipu_models_success():
    raw_data = {
        "data": [
            {"id": "glm-4-plus", "context_length": 128000},
            {"id": "glm-4-flash"},
            {"id": ""},
            {"missing_id": True},
        ]
    }
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_zhipu_models(api_key="zhipu_api_key_xyz", force=True)

        mock_get.assert_called_once_with(
            CATALOG_URL,
            headers={"Authorization": "Bearer zhipu_api_key_xyz"},
            timeout=10,
        )
        assert len(models) == 2
        assert models[0]["id"] == "glm-4-plus"
        assert models[0]["name"] == "glm-4-plus"
        assert models[0]["description"] == ""
        assert models[0]["context_length"] == 0
        assert models[0]["pricing"] == {}
        assert models[1]["id"] == "glm-4-flash"


def test_fetch_zhipu_models_without_api_key():
    raw_data = {"data": [{"id": "glm-4-air"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_zhipu_models(api_key="", force=True)

        mock_get.assert_called_once_with(CATALOG_URL, headers={}, timeout=10)
        assert len(models) == 1
        assert models[0]["id"] == "glm-4-air"


def test_fetch_zhipu_models_caching():
    raw_data = {"data": [{"id": "glm-1"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        res1 = fetch_zhipu_models()
        res2 = fetch_zhipu_models()

        assert mock_get.call_count == 1
        assert res1 == res2


def test_fetch_zhipu_models_force_refresh():
    raw_data = {"data": [{"id": "glm-fresh"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        with zc._cache_lock:
            zc._cache["data"] = [{"id": "cached"}]
            zc._cache["fetched_at"] = time.time()

        res = fetch_zhipu_models(force=True)
        assert mock_get.call_count == 1
        assert res[0]["id"] == "glm-fresh"


def test_fetch_zhipu_models_network_failure_returns_empty_list():
    with patch("requests.get", side_effect=Exception("Zhipu API error")):
        models = fetch_zhipu_models(force=True)
        assert models == []


def test_fetch_zhipu_models_network_failure_returns_stale_cache():
    stale_data = [{"id": "stale-glm", "name": "stale-glm"}]
    with zc._cache_lock:
        zc._cache["data"] = stale_data
        zc._cache["fetched_at"] = time.time()

    with patch("requests.get", side_effect=Exception("Zhipu API error")):
        models = fetch_zhipu_models(force=True)
        assert models == stale_data


def test_search_zhipu_models_default_args():
    sample_models = [
        {"id": "glm-4-plus", "name": "glm-4-plus", "pricing": {}},
        {"id": "glm-4-flash", "name": "glm-4-flash", "pricing": {}},
    ]
    with patch("app.utils.zhipu_catalog.fetch_zhipu_models", return_value=sample_models):
        res = search_zhipu_models(query="")
        assert len(res) == 2


def test_search_zhipu_models_query_filtering():
    sample_models = [
        {"id": "glm-4-plus", "name": "glm-4-plus", "pricing": {}},
        {"id": "cogview-3-plus", "name": "cogview-3-plus", "pricing": {}},
    ]
    with patch("app.utils.zhipu_catalog.fetch_zhipu_models", return_value=sample_models):
        res_id = search_zhipu_models("cogview")
        assert len(res_id) == 1
        assert res_id[0]["id"] == "cogview-3-plus"

        res_case = search_zhipu_models("GLM")
        assert len(res_case) == 1
        assert res_case[0]["id"] == "glm-4-plus"


def test_search_zhipu_models_free_only_filtering():
    sample_models = [
        {"id": "glm-free", "name": "glm-free", "pricing": {"prompt": "0"}},
        {"id": "glm-paid", "name": "glm-paid", "pricing": {"prompt": "0.01"}},
    ]
    with patch("app.utils.zhipu_catalog.fetch_zhipu_models", return_value=sample_models):
        models = search_zhipu_models("")
        free_models = [m for m in models if m.get("pricing", {}).get("prompt") == "0"]
        assert len(free_models) == 1
        assert free_models[0]["id"] == "glm-free"


def test_search_zhipu_models_limit_truncation():
    sample_models = [{"id": f"glm-{i}", "name": f"glm-{i}", "pricing": {}} for i in range(10)]
    with patch("app.utils.zhipu_catalog.fetch_zhipu_models", return_value=sample_models):
        res = search_zhipu_models(query="", limit=4)
        assert len(res) == 4


def test_search_zhipu_models_network_failure_path():
    with patch("requests.get", side_effect=Exception("Timeout")):
        res = search_zhipu_models(query="")
        assert res == []
