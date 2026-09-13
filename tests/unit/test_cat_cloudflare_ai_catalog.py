"""Unit tests for app/utils/cloudflare_ai_catalog.py."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

import app.utils.cloudflare_ai_catalog as cfac
from app.utils.cloudflare_ai_catalog import (
    fetch_cloudflare_models,
    search_cloudflare_models,
)


@pytest.fixture(autouse=True)
def reset_cloudflare_cache():
    """Reset cache before and after each test."""
    with cfac._cache_lock:
        cfac._cache["data"] = None
        cfac._cache["fetched_at"] = 0.0
    yield
    with cfac._cache_lock:
        cfac._cache["data"] = None
        cfac._cache["fetched_at"] = 0.0


def test_fetch_cloudflare_models_default():
    models = fetch_cloudflare_models()
    assert len(models) >= 6
    assert any(m["id"] == "@cf/meta/llama-2-7b-chat-int8" for m in models)
    assert models[0]["description"] == ""
    assert models[0]["context_length"] == 0
    assert models[0]["pricing"] == {}


def test_fetch_cloudflare_models_caching():
    cached_data = [
        {
            "id": "@cf/custom",
            "name": "Custom",
            "description": "",
            "context_length": 0,
            "pricing": {},
        }
    ]
    with cfac._cache_lock:
        cfac._cache["data"] = cached_data
        cfac._cache["fetched_at"] = time.time()

    models = fetch_cloudflare_models(force=False)
    assert models == cached_data


def test_fetch_cloudflare_models_force_refresh():
    cached_data = [{"id": "@cf/custom", "name": "Custom"}]
    with cfac._cache_lock:
        cfac._cache["data"] = cached_data
        cfac._cache["fetched_at"] = time.time()

    models = fetch_cloudflare_models(force=True)
    assert models != cached_data
    assert any(m["id"] == "@cf/meta/llama-2-7b-chat-int8" for m in models)


def test_fetch_cloudflare_models_empty_returns_empty_list():
    with patch("app.utils.cloudflare_ai_catalog.MODELS_LIST", []):
        models = fetch_cloudflare_models(force=True)
        assert models == []


def test_search_cloudflare_models_default_args():
    models = search_cloudflare_models("")
    assert len(models) >= 6
    assert models[0]["id"].startswith("@cf/")


def test_search_cloudflare_models_query_filtering():
    # Filter by id substring
    res_id = search_cloudflare_models("qwen-1.8b")
    assert len(res_id) == 1
    assert res_id[0]["id"] == "@cf/qwen/qwen-1.8b-chat"

    # Filter by name substring
    res_name = search_cloudflare_models("OpenChat")
    assert len(res_name) == 1
    assert res_name[0]["id"] == "@cf/openchat/openchat-3.5-0106"

    # Case-insensitive
    res_case = search_cloudflare_models("MISTRAL")
    assert len(res_case) == 1
    assert res_case[0]["id"] == "@cf/mistral/mistral-7b-instruct-v0.1"


def test_search_cloudflare_models_free_only_filtering():
    # Cloudflare catalog entries have empty pricing dicts {}
    models = search_cloudflare_models("")
    assert all(isinstance(m["pricing"], dict) for m in models)
    # Testing caller filtering for free status
    free_models = [m for m in models if m.get("pricing") == {}]
    assert len(free_models) == len(models)


def test_search_cloudflare_models_limit_truncation():
    limited = search_cloudflare_models(query="", limit=2)
    assert len(limited) == 2


def test_search_cloudflare_models_network_failure_path():
    # When underlying fetch returns empty (simulating network/source failure)
    with patch("app.utils.cloudflare_ai_catalog.fetch_cloudflare_models", return_value=[]):
        results = search_cloudflare_models(query="")
        assert results == []
