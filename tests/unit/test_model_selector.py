"""Unit tests for app/utils/model_selector.py."""

from unittest.mock import MagicMock, patch

from app.utils.model_selector import (
    _build_ollama_router,
    _categorize_cloud_models,
)


def test_categorize_cloud_models_groups_by_host_map():
    """Test that cloud models are grouped by host_map entries."""
    # Create mock settings with models
    mock_settings = MagicMock()
    mock_settings.models = {
        "model1": MagicMock(base_url="https://api.x.ai/v1", backend="grok"),
        "model2": MagicMock(base_url="https://openrouter.ai/api/v1", backend="openrouter"),
        "model3": MagicMock(
            base_url="https://generativelanguage.googleapis.com/v1beta", backend="google"
        ),
        "model4": MagicMock(base_url="https://api.openai.com/v1", backend="openai"),
    }

    groups = _categorize_cloud_models(mock_settings)

    assert "grok" in groups
    assert "model1" in groups["grok"]
    assert "openrouter" in groups
    assert "model2" in groups["openrouter"]
    assert "google" in groups
    assert "model3" in groups["google"]
    # api.openai.com not in host_map, so falls back to netloc
    assert "api.openai.com" in groups
    assert "model4" in groups["api.openai.com"]


def test_categorize_cloud_models_localhost_uses_backend_map():
    """Test that localhost/127.0.0.1 models use backend_map."""
    mock_settings = MagicMock()
    mock_settings.models = {
        "local_google": MagicMock(base_url="http://localhost:8000", backend="google"),
        "local_unknown": MagicMock(base_url="http://127.0.0.1:8000", backend="unknown"),
    }

    groups = _categorize_cloud_models(mock_settings)

    assert "google" in groups
    assert "local_google" in groups["google"]
    # unknown backend not in backend_map, so skipped
    assert "unknown" not in groups


def test_categorize_cloud_models_empty_settings():
    """Test with empty models dict."""
    mock_settings = MagicMock()
    mock_settings.models = {}

    groups = _categorize_cloud_models(mock_settings)

    assert groups == {}


def test_categorize_cloud_models_multiple_per_provider():
    """Test multiple models per provider."""
    mock_settings = MagicMock()
    mock_settings.models = {
        "grok1": MagicMock(base_url="https://api.x.ai/v1", backend="grok"),
        "grok2": MagicMock(base_url="https://api.x.ai/v1", backend="grok"),
        "or1": MagicMock(base_url="https://openrouter.ai/api/v1", backend="openrouter"),
    }

    groups = _categorize_cloud_models(mock_settings)

    assert len(groups["grok"]) == 2
    assert len(groups["openrouter"]) == 1


def test_build_ollama_router_success():
    """Test _build_ollama_router returns True on success."""
    mock_switcher = MagicMock()
    mock_switcher._routers = {}
    mock_switcher._active_profile = None

    with (
        patch("app.models.ollama_client.OllamaClient") as mock_ollama_class,
        patch("app.models.router.ModelRouter") as mock_router_class,
        patch("app.models.router.TaskType") as mock_task_type,
    ):
        mock_client = MagicMock()
        mock_ollama_class.return_value = mock_client

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        # TaskType constructor for role strings
        mock_task_type.side_effect = lambda r: r

        result = _build_ollama_router(mock_switcher, "llama3", "http://localhost:11434")

        assert result is True
        mock_ollama_class.assert_called_once_with(
            model="llama3", base_url="http://localhost:11434", role="general"
        )

        # Should register for all 6 roles
        assert mock_router.register.call_count == 6
        called_roles = [call[0][0] for call in mock_router.register.call_args_list]
        assert set(called_roles) == {"general", "code", "reasoning", "docs", "stem", "autocomplete"}

        mock_router.set_default.assert_called_once_with(mock_client)
        assert "ollama:llama3" in mock_switcher._routers
        assert mock_switcher._active_profile == "ollama:llama3"


def test_build_ollama_router_failure():
    """Test _build_ollama_router returns False on client creation failure."""
    mock_switcher = MagicMock()
    mock_switcher._routers = {}

    with patch(
        "app.models.ollama_client.OllamaClient", side_effect=RuntimeError("connection refused")
    ):
        result = _build_ollama_router(mock_switcher, "llama3", "http://localhost:11434")

        assert result is False
        assert "ollama:llama3" not in mock_switcher._routers


def test_build_ollama_router_register_failure_continues():
    """Test that registration failures for some roles don't break the whole thing."""
    mock_switcher = MagicMock()
    mock_switcher._routers = {}
    mock_switcher._active_profile = None

    with (
        patch("app.models.ollama_client.OllamaClient") as mock_ollama_class,
        patch("app.models.router.ModelRouter") as mock_router_class,
        patch("app.models.router.TaskType") as mock_task_type,
    ):
        mock_client = MagicMock()
        mock_ollama_class.return_value = mock_client

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        # Make one role fail
        def task_type_side_effect(role):
            if role == "code":
                raise ValueError("bad role")
            return role

        mock_task_type.side_effect = task_type_side_effect

        result = _build_ollama_router(mock_switcher, "llama3", "http://localhost:11434")

        assert result is True
        # Should still have registered 5 of 6 roles
        assert mock_router.register.call_count == 5
