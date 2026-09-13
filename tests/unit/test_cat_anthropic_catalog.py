"""Unit tests for app/utils/anthropic_catalog.py."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

import app.utils.anthropic_catalog as ac
from app.utils.anthropic_catalog import (
    fetch_anthropic_models,
    is_free_model,
    search_anthropic_models,
)


@pytest.fixture(autouse=True)
def reset_anthropic_cache():
    """Reset cache before and after each test."""
    with ac._cache_lock:
        ac._cache["data"] = None
        ac._cache["fetched_at"] = 0.0
    yield
    with ac._cache_lock:
        ac._cache["data"] = None
        ac._cache["fetched_at"] = 0.0


def test_fetch_anthropic_models_default():
    models = fetch_anthropic_models()
    assert len(models) >= 5
    assert any(m["id"] == "claude-3-5-sonnet-20241022" for m in models)
    # Check that cache was populated
    with ac._cache_lock:
        assert ac._cache["data"] is not None
        assert ac._cache["fetched_at"] > 0.0


def test_fetch_anthropic_models_caching():
    # Pre-populate cache with a mock object
    cached_data = [
        {"id": "claude-custom", "name": "Claude Custom", "context_length": 100000, "pricing": {}}
    ]
    with ac._cache_lock:
        ac._cache["data"] = cached_data
        ac._cache["fetched_at"] = time.time()

    models = fetch_anthropic_models(force=False)
    assert models == cached_data


def test_fetch_anthropic_models_force_refresh():
    cached_data = [{"id": "claude-custom", "name": "Claude Custom"}]
    with ac._cache_lock:
        ac._cache["data"] = cached_data
        ac._cache["fetched_at"] = time.time()

    models = fetch_anthropic_models(force=True)
    assert models != cached_data
    assert any(m["id"] == "claude-3-5-sonnet-20241022" for m in models)


def test_is_free_model():
    assert is_free_model({}) is False
    assert is_free_model({"pricing": {"prompt": "0", "completion": "0"}}) is False


def test_search_anthropic_models_default_args():
    models = search_anthropic_models("")
    assert len(models) >= 5
    # Verify sorted by (context_length, id) descending
    for i in range(len(models) - 1):
        k1 = (models[i]["context_length"], models[i]["id"])
        k2 = (models[i + 1]["context_length"], models[i + 1]["id"])
        assert k1 >= k2


def test_search_anthropic_models_free_only():
    # Anthropic models are never free, so free_only returns empty list
    models = search_anthropic_models(query="", free_only=True)
    assert models == []


def test_search_anthropic_models_query_filtering():
    # Substring matching id
    results_id = search_anthropic_models("haiku-20241022")
    assert len(results_id) == 1
    assert results_id[0]["id"] == "claude-3-5-haiku-20241022"

    # Substring matching name
    results_name = search_anthropic_models("Opus")
    assert len(results_name) == 1
    assert results_name[0]["id"] == "claude-3-opus-20240229"

    # Case-insensitive
    results_case = search_anthropic_models("SONNET")
    assert len(results_case) >= 2
    assert all("sonnet" in m["name"].lower() or "sonnet" in m["id"].lower() for m in results_case)


def test_search_anthropic_models_limit_truncation():
    results = search_anthropic_models(query="", limit=2)
    assert len(results) == 2


def test_search_anthropic_models_network_failure_or_empty_catalog():
    # When catalog source returns empty or fails
    with patch("app.utils.anthropic_catalog.fetch_anthropic_models", return_value=[]):
        results = search_anthropic_models(query="")
        assert results == []
