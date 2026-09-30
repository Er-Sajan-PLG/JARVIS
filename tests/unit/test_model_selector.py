"""Unit tests for app/utils/model_selector.py.

``_build_ollama_router`` no longer builds a ``ModelRouter`` -- see
``tests/unit/test_router_call_sites.py`` -- it maps the chosen Ollama model to a
real ``ModelClient`` profile on the switcher. The rest of these tests drive the
startup menu, whose "default" entry renders the client that profile holds. That
read was ``.default_model.model_name`` -- an attribute no client has -- until
2026-09-30; ``test_startup_model_select_renders_a_real_default_profile`` drives
the real path so a regression to it raises instead of hiding behind a mock.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models.client import ModelClient
from app.models.switcher import ModelSwitcher
from app.utils.model_selector import (
    _build_ollama_router,
    _categorize_cloud_models,
    _startup_model_select,
)


def _stub_client(model_name: str = "llama3", role: str = "general") -> MagicMock:
    """A stand-in that actually satisfies the ModelClient protocol."""
    client = MagicMock(spec=ModelClient)
    client.model_name = model_name
    client.role = role
    return client


def _make_settings(models: dict | None = None) -> MagicMock:
    settings = MagicMock()
    settings.models = models if models is not None else {}
    settings.active_profile = ""
    return settings


def _make_config(
    key: str, backend: str = "ollama", name: str | None = None, role: str = "general"
) -> MagicMock:
    cfg = MagicMock()
    cfg.key = key
    cfg.backend = backend
    cfg.name = name or key
    cfg.role = role
    return cfg


def _real_switcher(models: dict | None = None) -> ModelSwitcher:
    """A switcher over the given models; construction contacts no provider."""
    return ModelSwitcher(_make_settings(models))


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
    """The chosen Ollama model becomes the active profile, mapped to its client."""
    switcher = _real_switcher()
    client = _stub_client("llama3", "general")

    with patch("app.models.ollama_client.OllamaClient", return_value=client) as ollama_class:
        result = _build_ollama_router(switcher, "llama3", "http://localhost:11434")

    assert result is True
    ollama_class.assert_called_once_with(
        model="llama3", base_url="http://localhost:11434", role="general"
    )
    assert isinstance(client, ModelClient)
    assert switcher._routers["ollama:llama3"] is client
    assert switcher.active_profile == "ollama:llama3"
    assert switcher.router is client
    assert switcher.switch("ollama:llama3") is True


def test_build_ollama_router_failure():
    """Test _build_ollama_router returns False on client creation failure."""
    switcher = _real_switcher()

    with patch(
        "app.models.ollama_client.OllamaClient", side_effect=RuntimeError("connection refused")
    ):
        result = _build_ollama_router(switcher, "llama3", "http://localhost:11434")

    assert result is False
    assert "ollama:llama3" not in switcher._routers
    assert switcher.active_profile == ""


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
    # The "default" profile holds a ModelClient; the menu renders its model_name.
    mock_default_router = _stub_client("llama3-small")
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


def test_startup_model_select_renders_a_real_default_profile(capsys):
    """The "default" entry renders the client the switcher actually holds.

    ``_startup_model_select`` reads ``switcher._routers["default"]``, which is a
    ``ModelClient`` since the switcher stopped building ``ModelRouter``s. It read
    ``.default_model.model_name`` until 2026-09-30 -- an attribute no client has,
    which the mock in the sibling test above answered for it. This test drives
    the real path, so a regression to that read raises AttributeError here.
    """
    settings = _make_settings({"local": _make_config("local", "ollama", "Small-1.5B")})
    with patch("app.models.switcher.create_client", return_value=_stub_client("Small-1.5B")):
        switcher = ModelSwitcher(settings)
    assert "default" in switcher._routers  # precondition: the entry is built

    with (
        patch("app.utils.model_selector.ollama_model_names", return_value=[]),
        patch("app.utils.model_selector.llamacpp_live_models", return_value=[]),
        patch("app.utils.model_selector._categorize_cloud_models", return_value={}),
        patch.dict("os.environ", {}, clear=True),
        patch("builtins.input", side_effect=[""]),
    ):
        _startup_model_select(switcher, settings)

    assert "Small-1.5B — local default" in capsys.readouterr().out


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
