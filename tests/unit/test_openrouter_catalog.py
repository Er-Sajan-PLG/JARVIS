"""Unit tests for app/utils/openrouter_catalog.py."""

import time
from unittest.mock import MagicMock, patch

from app.utils.openrouter_catalog import (
    _cache,
    fetch_openrouter_models,
    is_free_model,
    search_openrouter_models,
)


def test_fetch_openrouter_models_returns_parsed_data():
    """Test fetch_openrouter_models parses response correctly."""
    fake_response = {
        "data": [
            {
                "id": "openrouter/test-model",
                "name": "Test Model",
                "description": "A test model",
                "context_length": 8192,
                "pricing": {"prompt": "0", "completion": "0"},
            },
            {
                "id": "openrouter/paid-model",
                "name": "Paid Model",
                "description": "A paid model",
                "context_length": 32768,
                "pricing": {"prompt": "0.01", "completion": "0.02"},
            },
        ]
    }

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = fake_response
        mock_get.return_value = mock_resp

        _cache["data"] = None
        _cache["fetched_at"] = 0.0

        models = fetch_openrouter_models(force=True)

        assert len(models) == 2
        assert models[0]["id"] == "openrouter/test-model"
        assert models[0]["name"] == "Test Model"
        assert models[0]["context_length"] == 8192
        assert models[0]["pricing"] == {"prompt": "0", "completion": "0"}
        assert models[1]["id"] == "openrouter/paid-model"


def test_fetch_openrouter_models_caches_result():
    """Test fetch_openrouter_models caches the result."""
    fake_response = {
        "data": [{"id": "model1", "name": "Model 1", "context_length": 1000, "pricing": {}}]
    }

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = fake_response
        mock_get.return_value = mock_resp

        _cache["data"] = None
        _cache["fetched_at"] = 0.0

        # First call
        fetch_openrouter_models(force=True)
        # Second call without force should use cache
        fetch_openrouter_models(force=False)

        # requests.get should only be called once
        assert mock_get.call_count == 1


def test_fetch_openrouter_models_forces_refresh():
    """Test force=True bypasses cache."""
    fake_response = {
        "data": [{"id": "model1", "name": "Model 1", "context_length": 1000, "pricing": {}}]
    }

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = fake_response
        mock_get.return_value = mock_resp

        _cache["data"] = [{"id": "cached", "name": "Cached"}]
        _cache["fetched_at"] = time.time()

        fetch_openrouter_models(force=True)

        # Should still call requests.get
        assert mock_get.call_count == 1


def test_fetch_openrouter_models_returns_stale_cache_on_error():
    """Test fetch_openrouter_models returns stale cache on network error."""
    _cache["data"] = [{"id": "stale", "name": "Stale Model"}]
    _cache["fetched_at"] = time.time()

    with patch("requests.get", side_effect=Exception("network down")):
        models = fetch_openrouter_models(force=True)

        assert models == [{"id": "stale", "name": "Stale Model"}]


def test_fetch_openrouter_models_returns_empty_on_error_no_cache():
    """Test fetch_openrouter_models returns empty list on error with no cache."""
    _cache["data"] = None
    _cache["fetched_at"] = 0.0

    with patch("requests.get", side_effect=Exception("network down")):
        models = fetch_openrouter_models(force=True)

        assert models == []


def test_is_free_model_detects_free():
    """Test is_free_model returns True for zero pricing."""
    assert is_free_model({"pricing": {"prompt": "0", "completion": "0"}}) is True
    assert is_free_model({"pricing": {"prompt": "0.0", "completion": "0.0"}}) is True


def test_is_free_model_detects_paid():
    """Test is_free_model returns False for non-zero pricing."""
    assert is_free_model({"pricing": {"prompt": "0.01", "completion": "0.02"}}) is False
    assert is_free_model({"pricing": {"prompt": "0", "completion": "0.01"}}) is False


def test_is_free_model_handles_missing_pricing():
    """Test is_free_model returns False for missing/empty pricing."""
    assert is_free_model({}) is False
    assert is_free_model({"pricing": {}}) is False
    assert is_free_model({"pricing": None}) is False


def test_search_openrouter_models_filters_by_query():
    """Test search_openrouter_models filters by query string."""
    fake_models = [
        {"id": "model-a", "name": "Alpha", "context_length": 1000, "pricing": {}},
        {"id": "model-b", "name": "Beta", "context_length": 2000, "pricing": {}},
        {"id": "other", "name": "Gamma", "context_length": 3000, "pricing": {}},
    ]

    with patch("app.utils.openrouter_catalog.fetch_openrouter_models", return_value=fake_models):
        # Query matching id
        results = search_openrouter_models(query="model-a")
        assert len(results) == 1
        assert results[0]["id"] == "model-a"

        # Query matching name
        results = search_openrouter_models(query="beta")
        assert len(results) == 1
        assert results[0]["id"] == "model-b"

        # Case insensitive
        results = search_openrouter_models(query="ALPHA")
        assert len(results) == 1


def test_search_openrouter_models_free_only():
    """Test search_openrouter_models with free_only=True."""
    fake_models = [
        {
            "id": "free-model",
            "name": "Free Model",
            "context_length": 1000,
            "pricing": {"prompt": "0", "completion": "0"},
        },
        {
            "id": "paid-model",
            "name": "Paid Model",
            "context_length": 2000,
            "pricing": {"prompt": "0.01", "completion": "0.02"},
        },
    ]

    with patch("app.utils.openrouter_catalog.fetch_openrouter_models", return_value=fake_models):
        results = search_openrouter_models(query="", free_only=True)
        assert len(results) == 1
        assert results[0]["id"] == "free-model"


def test_search_openrouter_models_limit():
    """Test search_openrouter_models respects limit."""
    fake_models = [
        {"id": f"model-{i}", "name": f"Model {i}", "context_length": 1000 * i, "pricing": {}}
        for i in range(10)
    ]

    with patch("app.utils.openrouter_catalog.fetch_openrouter_models", return_value=fake_models):
        results = search_openrouter_models(query="", limit=3)
        assert len(results) == 3


def test_search_openrouter_models_empty_query_returns_all():
    """Test search_openrouter_models with empty query returns all (sorted)."""
    fake_models = [
        {"id": "small", "name": "Small", "context_length": 1000, "pricing": {}},
        {"id": "large", "name": "Large", "context_length": 100000, "pricing": {}},
    ]

    with patch("app.utils.openrouter_catalog.fetch_openrouter_models", return_value=fake_models):
        results = search_openrouter_models(query="")
        assert len(results) == 2
        # Should be sorted by context_length descending
        assert results[0]["id"] == "large"
        assert results[1]["id"] == "small"


def test_search_openrouter_models_stable_sorting():
    """Test search_openrouter_models sorts by context_length then id."""
    fake_models = [
        {"id": "a", "name": "A", "context_length": 5000, "pricing": {}},
        {"id": "b", "name": "B", "context_length": 5000, "pricing": {}},
    ]

    with patch("app.utils.openrouter_catalog.fetch_openrouter_models", return_value=fake_models):
        results = search_openrouter_models(query="")
        # Both have same context_length, so sorted by id
        assert results[0]["id"] == "b"  # reverse=True
        assert results[1]["id"] == "a"
