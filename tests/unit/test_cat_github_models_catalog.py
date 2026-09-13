"""Unit tests for app/utils/github_models_catalog.py."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

import app.utils.github_models_catalog as ghc
from app.utils.github_models_catalog import (
    fetch_github_models,
    search_github_models,
)


@pytest.fixture(autouse=True)
def reset_github_cache():
    """Reset cache before and after each test."""
    with ghc._cache_lock:
        ghc._cache["data"] = None
        ghc._cache["fetched_at"] = 0.0
    yield
    with ghc._cache_lock:
        ghc._cache["data"] = None
        ghc._cache["fetched_at"] = 0.0


def test_fetch_github_models_default():
    models = fetch_github_models()
    assert len(models) >= 9
    assert any(m["id"] == "gpt-4o" for m in models)
    assert models[0]["description"] == ""
    assert models[0]["context_length"] == 0
    assert models[0]["pricing"] == {}


def test_fetch_github_models_caching():
    cached_data = [
        {"id": "gh-cached", "name": "Cached", "description": "", "context_length": 0, "pricing": {}}
    ]
    with ghc._cache_lock:
        ghc._cache["data"] = cached_data
        ghc._cache["fetched_at"] = time.time()

    models = fetch_github_models(force=False)
    assert models == cached_data


def test_fetch_github_models_force_refresh():
    cached_data = [{"id": "gh-cached", "name": "Cached"}]
    with ghc._cache_lock:
        ghc._cache["data"] = cached_data
        ghc._cache["fetched_at"] = time.time()

    models = fetch_github_models(force=True)
    assert models != cached_data
    assert any(m["id"] == "gpt-4o" for m in models)


def test_fetch_github_models_empty_returns_empty():
    with patch("app.utils.github_models_catalog.MODELS_LIST", []):
        models = fetch_github_models(force=True)
        assert models == []


def test_search_github_models_default_args():
    models = search_github_models("")
    assert len(models) >= 9


def test_search_github_models_query_filtering():
    # Search by id
    res_id = search_github_models("llama-3.1-405b")
    assert len(res_id) == 1
    assert res_id[0]["id"] == "llama-3.1-405b-instruct"

    # Search by name
    res_name = search_github_models("Phi-3.5 Mini")
    assert len(res_name) == 1
    assert res_name[0]["id"] == "phi-3.5-mini-instruct"

    # Case-insensitive
    res_case = search_github_models("MISTRAL")
    assert len(res_case) == 2
    assert all("mistral" in m["id"].lower() for m in res_case)


def test_search_github_models_free_only_filtering():
    # GitHub models entries default to empty pricing dict
    models = search_github_models("")
    assert all(isinstance(m.get("pricing"), dict) for m in models)
    free_models = [m for m in models if m.get("pricing") == {}]
    assert len(free_models) == len(models)


def test_search_github_models_limit_truncation():
    limited = search_github_models(query="", limit=3)
    assert len(limited) == 3


def test_search_github_models_network_failure_path():
    with patch("app.utils.github_models_catalog.fetch_github_models", return_value=[]):
        assert search_github_models("") == []
