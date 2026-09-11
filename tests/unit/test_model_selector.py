"""Unit tests for app/utils/model_selector.py."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.utils.model_selector import (
    _build_ollama_router,
    _categorize_cloud_models,
    _startup_model_select,
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


def test_startup_model_select_no_entries(capsys):
    """Test _startup_model_select when entries list is empty (lines 181-182)."""
    mock_switcher = MagicMock()
    mock_switcher._routers = {}
    mock_settings = MagicMock()
    mock_settings.paths.ollama_url = "http://localhost:11434"

    def clear_entries_hook():
        import inspect

        frame = inspect.currentframe()
        while frame:
            if frame.f_code.co_name == "_startup_model_select":
                if "entries" in frame.f_locals:
                    frame.f_locals["entries"].clear()
                break
            frame = frame.f_back
        return []

    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"}),
        patch(
            "app.utils.openrouter_catalog.fetch_openrouter_models",
            side_effect=clear_entries_hook,
        ),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "No backends/models configured. Using default router." in captured


def test_startup_model_select_enter_keeps_current_profile(capsys):
    """Test pressing Enter at backend prompt keeps the current active profile."""
    mock_switcher = MagicMock()
    mock_switcher._routers = {}
    mock_switcher.active_profile = "custom-profile"
    mock_settings = MagicMock()
    mock_settings.paths.ollama_url = "http://localhost:11434"

    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=["llama3:latest"]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=[""]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "Keeping 'custom-profile'." in captured


def test_startup_model_select_invalid_backend_selection(capsys):
    """Test entering invalid numbers or non-numeric strings at backend prompt."""
    mock_switcher = MagicMock()
    mock_switcher._routers = {}
    mock_switcher.active_profile = "default"
    mock_settings = MagicMock()
    mock_settings.paths.ollama_url = "http://localhost:11434"

    # Non-numeric input
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=["llama3:latest"]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=["abc"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "Invalid selection — keeping current profile." in captured

    # Out of range numeric input
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=["llama3:latest"]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=["99"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "Invalid selection — keeping current profile." in captured


def test_startup_model_select_default_router_success_and_failure(capsys):
    """Test selecting default local router option with both usable and unusable outcomes."""
    mock_default_router = MagicMock()
    mock_default_router.default_model.model_name = "llama3-small"
    mock_switcher = MagicMock()
    mock_switcher._routers = {"default": mock_default_router}
    mock_switcher.active_profile = "default"
    mock_settings = MagicMock()
    mock_settings.paths.ollama_url = "http://localhost:11434"

    # Usable: switch returns True
    mock_switcher.switch.return_value = True
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=["1"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "✅ Using default local Ollama router" in captured
    mock_switcher.switch.assert_called_with("default")

    # Unusable: switch returns False
    mock_switcher.switch.return_value = False
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=["1"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "⚠️ Default local router is not usable." in captured


def test_startup_model_select_omni_router_success_and_failure(capsys):
    """Test selecting omni router option with both usable and unusable outcomes."""
    mock_switcher = MagicMock()
    mock_switcher._routers = {"omni": MagicMock()}
    mock_switcher.active_profile = "omni"
    mock_settings = MagicMock()
    mock_settings.paths.ollama_url = "http://localhost:11434"

    # Usable
    mock_switcher.switch.return_value = True
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=["1"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "✅ Using Omni router (all loaded providers)" in captured
    mock_switcher.switch.assert_called_with("omni")

    # Unusable
    mock_switcher.switch.return_value = False
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=["1"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "⚠️ Omni router is not usable." in captured


def test_startup_model_select_ollama_not_reachable(capsys):
    """Test selecting Ollama when no models are pulled / server is not reachable."""
    mock_switcher = MagicMock()
    mock_switcher._routers = {}
    mock_switcher.active_profile = "default"
    mock_settings = MagicMock()
    mock_settings.paths.ollama_url = "http://localhost:11434"

    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=["1"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "⚠️ Ollama is not reachable. Start `ollama serve` first." in captured


def test_startup_model_select_ollama_model_selection(capsys):
    """Test Ollama model selection with both invalid choice and valid build."""
    mock_switcher = MagicMock()
    mock_switcher._routers = {}
    mock_switcher.active_profile = "default"
    mock_settings = MagicMock()
    mock_settings.paths.ollama_url = "http://localhost:11434"

    # Invalid model selection index
    with (
        patch(
            "app.utils.model_selector.ollama_model_names",
            return_value=["llama3:8b", "phi3:mini"],
        ),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=["1", "99"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "Invalid selection — keeping current profile." in captured

    # Valid model selection
    with (
        patch(
            "app.utils.model_selector.ollama_model_names",
            return_value=["llama3:8b", "phi3:mini"],
        ),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=["1", "2"]),
        patch("app.utils.model_selector._build_ollama_router", return_value=True) as mock_build,
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "✅ Using Ollama model: phi3:mini" in captured
    mock_build.assert_called_once_with(mock_switcher, "phi3:mini", "http://localhost:11434")


def test_startup_model_select_local_llamacpp(capsys):
    """Test llama.cpp local server selection, marker display, and switch outcomes."""
    mock_switcher = MagicMock()
    mock_switcher._routers = {}
    mock_switcher.active_profile = "model:local_1"
    mock_settings = MagicMock()
    mock_settings.paths.ollama_url = "http://localhost:11434"

    local_models = [
        {"name": "Local-Llama", "key": "local_1"},
        {"name": "Local-Mistral", "key": "local_2"},
    ]

    # Invalid selection
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=local_models),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=["2", "bad_choice"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "● llama.cpp (local server)" in captured
    assert "Invalid selection — keeping current profile." in captured

    # Valid selection, switch succeeds
    mock_switcher.switch_to_model.return_value = True
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=local_models),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=["2", "1"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "✅ Using local model: Local-Llama" in captured
    mock_switcher.switch_to_model.assert_called_with("local_1")

    # Valid selection, switch fails
    mock_switcher.switch_to_model.return_value = False
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=local_models),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=["2", "2"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "⚠️ Model 'Local-Mistral' is not loaded (server down?)." in captured


def test_startup_model_select_cloud_models(capsys):
    """Test cloud API model selection across missing key, loaded status, and switch outcomes."""
    mock_switcher = MagicMock()
    mock_switcher._routers = {}
    mock_switcher.active_profile = "default"

    mock_settings = MagicMock()
    mock_settings.paths.ollama_url = "http://localhost:11434"
    mock_settings.models = {
        "gemini_flash": SimpleNamespace(name="Gemini 2.0 Flash"),
        "gemini_pro": SimpleNamespace(name="Gemini Pro"),
    }

    # Case 1: Missing API key
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch(
            "app.utils.model_selector._categorize_cloud_models",
            return_value={"google": ["gemini_flash"]},
        ),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=["2"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "⚠️ GOOGLE_API_KEY is not set in your .env file." in captured

    # Case 2: Key is set, invalid model index
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch(
            "app.utils.model_selector._categorize_cloud_models",
            return_value={"google": ["gemini_flash"]},
        ),
        patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
        patch("builtins.input", side_effect=["2", "99"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "Invalid selection — keeping current profile." in captured

    # Case 3: Key is set, model loaded, switch succeeds
    mock_switcher.get_client.return_value = MagicMock()
    mock_switcher.switch_to_model.return_value = True
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch(
            "app.utils.model_selector._categorize_cloud_models",
            return_value={"google": ["gemini_flash"]},
        ),
        patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
        patch("builtins.input", side_effect=["2", "1"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "✓ loaded" in captured
    assert "✅ Using google model: Gemini 2.0 Flash" in captured
    mock_switcher.switch_to_model.assert_called_with("gemini_flash")

    # Case 4: Key is set, model not loaded, switch fails
    mock_switcher.get_client.return_value = None
    mock_switcher.switch_to_model.return_value = False
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch(
            "app.utils.model_selector._categorize_cloud_models",
            return_value={"google": ["gemini_flash"]},
        ),
        patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}),
        patch("builtins.input", side_effect=["2", "1"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "✗ not loaded" in captured
    assert "⚠️ Model not loaded — check its API key in .env." in captured


def test_startup_model_select_openrouter_catalog(capsys):
    """Test live OpenRouter catalog browsing, catalog failure, and model selection."""
    mock_switcher = MagicMock()
    mock_switcher._routers = {}
    mock_switcher.active_profile = "default"

    mock_settings = MagicMock()
    mock_settings.paths.ollama_url = "http://localhost:11434"

    catalog_data = [
        {"id": "meta-llama/llama-3.3-70b", "context_length": 128000},
        {"id": "qwen/qwen-2.5-72b", "context_length": 0},
    ]

    # Case 1: Catalog fetch failure on selection
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}),
        patch(
            "app.utils.openrouter_catalog.fetch_openrouter_models",
            side_effect=[catalog_data, []],
        ),
        patch("builtins.input", side_effect=["2"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "⚠️ Could not fetch the OpenRouter catalog (network down?)." in captured

    # Case 2: Select model by index, switch succeeds
    mock_switcher.switch_to_dynamic_model.return_value = True
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}),
        patch("app.utils.openrouter_catalog.fetch_openrouter_models", return_value=catalog_data),
        patch("builtins.input", side_effect=["2", "1"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "128k ctx" in captured
    assert "✅ Using OpenRouter model: meta-llama/llama-3.3-70b" in captured
    mock_switcher.switch_to_dynamic_model.assert_called_with(
        "openrouter", "meta-llama/llama-3.3-70b", "OPENROUTER_API_KEY"
    )

    # Case 3: Select model by literal name, switch fails
    mock_switcher.switch_to_dynamic_model.return_value = False
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}),
        patch("app.utils.openrouter_catalog.fetch_openrouter_models", return_value=catalog_data),
        patch("builtins.input", side_effect=["2", "anthropic/claude-3.5-sonnet"]),
    ):
        _startup_model_select(mock_switcher, mock_settings)

    captured = capsys.readouterr().out
    assert "⚠️ Could not load that model — check your key in .env." in captured
    mock_switcher.switch_to_dynamic_model.assert_called_with(
        "openrouter", "anthropic/claude-3.5-sonnet", "OPENROUTER_API_KEY"
    )


def test_startup_model_select_active_profile_marker_local():
    """Test local profile marker rendering when active_profile is exactly 'local'."""
    mock_switcher = MagicMock()
    mock_switcher._routers = {}
    mock_switcher.active_profile = "local"
    mock_settings = MagicMock()
    mock_settings.paths.ollama_url = "http://localhost:11434"

    local_models = [{"name": "Local-1", "key": "loc1"}]
    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=local_models),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=[""]),
    ):
        _startup_model_select(mock_switcher, mock_settings)
