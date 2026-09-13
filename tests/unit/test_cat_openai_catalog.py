"""Unit tests for app/utils/openai_catalog.py."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

import app.utils.openai_catalog as oac
from app.utils.openai_catalog import (
    fetch_openai_models,
    is_free_model,
    search_openai_models,
)


@pytest.fixture(autouse=True)
def reset_openai_cache():
    """Reset cache before and after each test."""
    with oac._cache_lock:
        oac._cache["data"] = None
        oac._cache["fetched_at"] = 0.0
    yield
    with oac._cache_lock:
        oac._cache["data"] = None
        oac._cache["fetched_at"] = 0.0


def test_fetch_openai_models_default():
    models = fetch_openai_models()
    assert len(models) >= 7
    assert any(m["id"] == "gpt-4o" for m in models)
    with oac._cache_lock:
        assert oac._cache["data"] is not None
        assert oac._cache["fetched_at"] > 0.0


def test_fetch_openai_models_caching():
    cached_data = [{"id": "gpt-custom", "name": "Custom", "context_length": 128000, "pricing": {}}]
    with oac._cache_lock:
        oac._cache["data"] = cached_data
        oac._cache["fetched_at"] = time.time()

    models = fetch_openai_models(force=False)
    assert models == cached_data


def test_fetch_openai_models_force_refresh():
    cached_data = [{"id": "gpt-custom", "name": "Custom"}]
    with oac._cache_lock:
        oac._cache["data"] = cached_data
        oac._cache["fetched_at"] = time.time()

    models = fetch_openai_models(force=True)
    assert models != cached_data
    assert any(m["id"] == "gpt-4o" for m in models)


def test_is_free_model():
    assert is_free_model({}) is False
    assert is_free_model({"pricing": {"prompt": "0", "completion": "0"}}) is False


def test_search_openai_models_default_args():
    models = search_openai_models("")
    assert len(models) >= 7
    # Verify sorted by (context_length, id) descending
    for i in range(len(models) - 1):
        k1 = (models[i]["context_length"], models[i]["id"])
        k2 = (models[i + 1]["context_length"], models[i + 1]["id"])
        assert k1 >= k2


def test_search_openai_models_free_only():
    models = search_openai_models(query="", free_only=True)
    assert models == []


def test_search_openai_models_query_filtering():
    # ID substring
    res_id = search_openai_models("o1-mini")
    assert len(res_id) == 1
    assert res_id[0]["id"] == "o1-mini"

    # Name substring
    res_name = search_openai_models("Preview")
    assert len(res_name) == 1
    assert res_name[0]["id"] == "o1-preview"

    # Case-insensitive
    res_case = search_openai_models("TURBO")
    assert len(res_case) >= 1
    assert any(m["id"] == "gpt-4-turbo" for m in res_case)


def test_search_openai_models_limit_truncation():
    results = search_openai_models(query="", limit=3)
    assert len(results) == 3


def test_search_openai_models_network_failure_or_empty_catalog():
    with patch("app.utils.openai_catalog.fetch_openai_models", return_value=[]):
        assert search_openai_models("") == []
