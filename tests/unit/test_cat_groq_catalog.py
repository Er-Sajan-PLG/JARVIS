"""Unit tests for app/utils/groq_catalog.py."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

import app.utils.groq_catalog as gc
from app.utils.groq_catalog import (
    CATALOG_URL,
    fetch_groq_models,
    search_groq_models,
)


@pytest.fixture(autouse=True)
def reset_groq_cache():
    """Reset cache before and after each test."""
    with gc._cache_lock:
        gc._cache["data"] = None
        gc._cache["fetched_at"] = 0.0
    yield
    with gc._cache_lock:
        gc._cache["data"] = None
        gc._cache["fetched_at"] = 0.0


def test_fetch_groq_models_success():
    raw_data = {
        "data": [
            {"id": "llama-3.1-70b-versatile", "context_window": 128000},
            {"id": "mixtral-8x7b-32768"},
            {"id": ""},
            {"other": "none"},
        ]
    }
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_groq_models(api_key="groq-key-123", force=True)

        mock_get.assert_called_once_with(
            CATALOG_URL,
            headers={"Authorization": "Bearer groq-key-123"},
            timeout=10,
        )
        assert len(models) == 2
        assert models[0]["id"] == "llama-3.1-70b-versatile"
        assert models[0]["name"] == "llama-3.1-70b-versatile"
        assert models[0]["description"] == ""
        assert models[0]["context_length"] == 0
        assert models[0]["pricing"] == {}
        assert models[1]["id"] == "mixtral-8x7b-32768"


def test_fetch_groq_models_without_explicit_key_uses_env(monkeypatch):
    """An empty api_key falls back to GROQ_API_KEY from the environment."""
    monkeypatch.setenv("GROQ_API_KEY", "env-key-123")
    raw_data = {"data": [{"id": "gemma2-9b-it"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_groq_models(api_key="", force=True)

        mock_get.assert_called_once_with(
            CATALOG_URL, headers={"Authorization": "Bearer env-key-123"}, timeout=10
        )
        assert len(models) == 1


def test_fetch_groq_models_without_any_key(monkeypatch):
    """With no key anywhere, the request goes out unauthenticated."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    raw_data = {"data": [{"id": "gemma2-9b-it"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        models = fetch_groq_models(api_key="", force=True)

        mock_get.assert_called_once_with(CATALOG_URL, headers={}, timeout=10)
        assert len(models) == 1


def test_fetch_groq_models_caching():
    raw_data = {"data": [{"id": "model-1"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        res1 = fetch_groq_models()
        res2 = fetch_groq_models()

        assert mock_get.call_count == 1
        assert res1 == res2


def test_fetch_groq_models_force_refresh():
    raw_data = {"data": [{"id": "fresh-groq"}]}
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = raw_data
        mock_get.return_value = mock_resp

        with gc._cache_lock:
            gc._cache["data"] = [{"id": "cached"}]
            gc._cache["fetched_at"] = time.time()

        res = fetch_groq_models(force=True)
        assert mock_get.call_count == 1
        assert res[0]["id"] == "fresh-groq"


def test_fetch_groq_models_network_failure_returns_empty_list():
    with patch("requests.get", side_effect=Exception("Groq API unreachable")):
        models = fetch_groq_models(force=True)
        assert models == []


def test_fetch_groq_models_network_failure_returns_stale_cache():
    stale_data = [{"id": "stale-groq", "name": "stale-groq"}]
    with gc._cache_lock:
        gc._cache["data"] = stale_data
        gc._cache["fetched_at"] = time.time()

    with patch("requests.get", side_effect=Exception("Groq API unreachable")):
        models = fetch_groq_models(force=True)
        assert models == stale_data


def test_search_groq_models_default_args():
    sample_models = [
        {"id": "llama-3.1-8b-instant", "name": "llama-3.1-8b-instant", "pricing": {}},
        {"id": "llama-3.1-70b-versatile", "name": "llama-3.1-70b-versatile", "pricing": {}},
    ]
    with patch("app.utils.groq_catalog.fetch_groq_models", return_value=sample_models):
        res = search_groq_models(query="")
        assert len(res) == 2


def test_search_groq_models_query_filtering():
    sample_models = [
        {"id": "llama-3.1-8b-instant", "name": "llama-3.1-8b-instant", "pricing": {}},
        {"id": "gemma2-9b-it", "name": "gemma2-9b-it", "pricing": {}},
    ]
    with patch("app.utils.groq_catalog.fetch_groq_models", return_value=sample_models):
        res_id = search_groq_models("gemma")
        assert len(res_id) == 1
        assert res_id[0]["id"] == "gemma2-9b-it"

        res_case = search_groq_models("LLAMA")
        assert len(res_case) == 1
        assert res_case[0]["id"] == "llama-3.1-8b-instant"


def test_search_groq_models_free_only_filtering():
    sample_models = [
        {"id": "free-groq", "name": "free-groq", "pricing": {"prompt": "0"}},
        {"id": "paid-groq", "name": "paid-groq", "pricing": {"prompt": "0.05"}},
    ]
    with patch("app.utils.groq_catalog.fetch_groq_models", return_value=sample_models):
        models = search_groq_models("")
        free_models = [m for m in models if m.get("pricing", {}).get("prompt") == "0"]
        assert len(free_models) == 1
        assert free_models[0]["id"] == "free-groq"


def test_search_groq_models_limit_truncation():
    sample_models = [{"id": f"model-{i}", "name": f"model-{i}", "pricing": {}} for i in range(10)]
    with patch("app.utils.groq_catalog.fetch_groq_models", return_value=sample_models):
        res = search_groq_models(query="", limit=3)
        assert len(res) == 3


def test_search_groq_models_network_failure_path():
    with patch("requests.get", side_effect=Exception("Timeout")):
        res = search_groq_models(query="")
        assert res == []
