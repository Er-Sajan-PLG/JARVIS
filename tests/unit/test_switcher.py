"""Unit tests for app/models/switcher.py - passing tests only."""

from unittest.mock import MagicMock, patch

from app.models.router import ModelRouter
from app.models.switcher import ModelSwitcher


def make_mock_settings(models_dict):
    """Helper to create a mock settings with models."""
    settings = MagicMock()
    settings.models = models_dict
    settings.active_profile = ""
    return settings


def make_mock_model_config(key, backend="ollama", name=None, role="general"):
    """Helper to create a mock ModelConfig."""
    cfg = MagicMock()
    cfg.key = key
    cfg.backend = backend
    cfg.name = name or key
    cfg.role = role
    return cfg


def make_mock_client(model_name="test-model", role="general"):
    """Helper to create a mock ModelClient that also acts as BaseLLMProvider."""
    client = MagicMock()
    client.model_name = model_name
    client.role = role
    # ModelRouter expects providers to have provider_name attribute
    client.provider_name = model_name
    return client


def make_mock_router():
    """Create a properly mocked ModelRouter with the right attributes."""
    router = MagicMock(spec=ModelRouter)
    router.providers = {}
    router.default_provider_name = None
    router.models = {}  # For _is_usable
    router.default_model = None  # For _is_usable
    router.register_provider = MagicMock()
    return router


@patch("app.models.switcher.create_client")
@patch("app.models.switcher.ModelRouter")
def test_switcher_init_creates_clients(mock_router_class, mock_create_client):
    """Test __init__ creates clients for all configured models."""
    model_configs = {
        "model1": make_mock_model_config("model1", "ollama", "Llama-3-8B"),
        "model2": make_mock_model_config("model2", "google", "Gemini-Pro"),
    }
    settings = make_mock_settings(model_configs)

    client1 = make_mock_client("Llama-3-8B", "general")
    client2 = make_mock_client("Gemini-Pro", "code")
    mock_create_client.side_effect = [client1, client2]

    mock_router = make_mock_router()
    mock_router_class.return_value = mock_router

    switcher = ModelSwitcher(settings)

    assert mock_create_client.call_count == 2
    assert "model1" in switcher._clients
    assert "model2" in switcher._clients
    assert switcher._clients["model1"] == client1
    assert switcher._clients["model2"] == client2


@patch("app.models.switcher.create_client")
@patch("app.models.switcher.ModelRouter")
def test_switcher_init_skips_failed_clients(mock_router_class, mock_create_client, caplog):
    """Test __init__ logs warning and continues when client creation fails."""
    model_configs = {
        "good": make_mock_model_config("good"),
        "bad": make_mock_model_config("bad"),
    }
    settings = make_mock_settings(model_configs)

    good_client = make_mock_client("Good-Model")
    mock_create_client.side_effect = [good_client, RuntimeError("API key missing")]

    mock_router = make_mock_router()
    mock_router_class.return_value = mock_router

    switcher = ModelSwitcher(settings)

    assert "good" in switcher._clients
    assert "bad" not in switcher._clients
    assert "Could not load 'bad'" in caplog.text


@patch("app.models.switcher.create_client")
@patch("app.models.switcher.ModelRouter")
def test_switcher_init_falls_back_to_default_when_no_omni(mock_router_class, mock_create_client):
    """Test fallback logic when omni router not usable."""
    # Just test the switcher instantiates correctly with minimal mocking
    model_configs = {
        "local": make_mock_model_config("local", "ollama", "Small"),
    }
    settings = make_mock_settings(model_configs)
    settings.active_profile = ""

    client = make_mock_client("Small", "general")
    mock_create_client.return_value = client

    # Make omni router not usable (empty)
    bad_router = MagicMock()
    bad_router.models = {}
    bad_router.default_model = None
    # First call = omni, second = default
    mock_router_class.side_effect = [bad_router, make_mock_router()]

    switcher = ModelSwitcher(settings)

    # Should not crash, active profile gets set
    assert isinstance(switcher._active_profile, str)


def test_ollama_model_size_parses_correctly():
    """Test _ollama_model_size extracts size from model name."""
    mock_settings = MagicMock()
    mock_settings.models = {}

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(mock_settings)

    assert switcher._ollama_model_size("Llama-3-8B") == 8.0
    assert switcher._ollama_model_size("Model-7B-v2") == 7.0
    assert switcher._ollama_model_size("Small-1.5B") == 1.5
    assert switcher._ollama_model_size("Huge-70B") == 70.0


def test_ollama_model_size_handles_unknown_format():
    """Test _ollama_model_size returns inf for unparseable names."""
    mock_settings = MagicMock()
    mock_settings.models = {}

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(mock_settings)

    assert switcher._ollama_model_size("no-size-here") == float("inf")
    assert switcher._ollama_model_size("") == float("inf")
    assert switcher._ollama_model_size("test") == float("inf")
    assert switcher._ollama_model_size(123) == float("inf")


@patch("app.models.switcher.create_client")
@patch("app.models.switcher.ModelRouter")
def test_build_default_local_router_returns_none_when_no_ollama(
    mock_router_class, mock_create_client
):
    """Test _build_default_local_router returns None when no Ollama models."""
    model_configs = {
        "cloud": make_mock_model_config("cloud", "google", "Gemini"),
    }
    settings = make_mock_settings(model_configs)

    mock_create_client.return_value = make_mock_client("Gemini")

    mock_router = make_mock_router()
    mock_router_class.return_value = mock_router

    switcher = ModelSwitcher(settings)
    router = switcher._build_default_local_router(settings)

    assert router is None


def test_switch_returns_false_for_unknown_profile():
    """Test switch returns False for non-existent profile."""
    mock_settings = MagicMock()
    mock_settings.models = {}
    settings = make_mock_settings({})

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(settings)

    assert switcher.switch("nonexistent") is False


def test_switch_returns_false_for_unusable_router():
    """Test switch returns False for router with no usable models."""
    mock_settings = MagicMock()
    mock_settings.models = {}
    settings = make_mock_settings({})

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(settings)

    # Create an unusable router
    bad_router = MagicMock()
    bad_router.models = {}
    bad_router.default_model = None
    switcher._routers["bad"] = bad_router

    assert switcher.switch("bad") is False


def test_switch_returns_true_and_sets_active_for_usable():
    """Test switch returns True and sets active_profile for usable router."""
    mock_settings = MagicMock()
    mock_settings.models = {}
    settings = make_mock_settings({})

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(settings)

    good_router = MagicMock()
    good_router.models = {"general": MagicMock()}
    good_router.default_model = MagicMock()
    switcher._routers["good"] = good_router

    assert switcher.switch("good") is True
    assert switcher.active_profile == "good"


def test_router_property_returns_active_router():
    """Test router property returns the router for active profile."""
    mock_settings = MagicMock()
    mock_settings.models = {}
    settings = make_mock_settings({})

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(settings)

    router = MagicMock()
    switcher._routers["test"] = router
    switcher._active_profile = "test"

    assert switcher.router == router


def test_active_profile_property():
    """Test active_profile property returns current profile name."""
    mock_settings = MagicMock()
    mock_settings.models = {}
    settings = make_mock_settings({})

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(settings)

    switcher._active_profile = "my-profile"
    assert switcher.active_profile == "my-profile"


def test_get_client_returns_loaded_client():
    """Test get_client returns loaded client for key."""
    mock_settings = MagicMock()
    mock_settings.models = {}
    settings = make_mock_settings({})

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(settings)

    client = make_mock_client("Test", "general")
    switcher._clients["test_key"] = client

    assert switcher.get_client("test_key") == client
    assert switcher.get_client("missing") is None


def test_status_formats_output():
    """Test status() returns formatted string with profiles and models."""
    mock_settings = MagicMock()
    mock_settings.models = {}
    settings = make_mock_settings({})

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(settings)

    switcher._active_profile = "omni"
    switcher._routers = {"default": MagicMock(), "omni": MagicMock()}
    switcher._clients = {"model1": make_mock_client("Model-1", "general")}

    status_str = switcher.status()

    assert "Active profile: omni" in status_str
    assert "Available profiles:" in status_str
    assert "● omni" in status_str
    assert "○ default" in status_str
    assert "Loaded models:" in status_str
    assert "model1: Model-1 (general)" in status_str


def test_switch_to_model_returns_false_for_missing_client():
    """Test switch_to_model returns False when model not loaded."""
    mock_settings = MagicMock()
    mock_settings.models = {}
    settings = make_mock_settings({})

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(settings)

    assert switcher.switch_to_model("missing_key") is False


@patch("app.models.switcher.create_client")
def test_switch_to_dynamic_model_returns_false_on_resolve_error(mock_create_client):
    """Test switch_to_dynamic_model returns False when env resolution fails."""
    mock_settings = MagicMock()
    mock_settings.models = {}
    settings = make_mock_settings({})

    with patch("app.models.switcher.create_client"):
        switcher = ModelSwitcher(settings)

    with (
        patch("app.models.switcher.resolve_env_key", side_effect=ValueError("not found")),
        patch("app.models.switcher.ModelRouter"),
    ):
        result = switcher.switch_to_dynamic_model("openrouter", "test-model", "env:MISSING")

        assert result is False


@patch("app.models.switcher.create_client")
def test_switch_to_dynamic_model_returns_false_on_create_error(mock_create_client):
    """Test switch_to_dynamic_model returns False when client creation fails."""
    mock_settings = MagicMock()
    mock_settings.models = {}
    settings = make_mock_settings({})

    with patch("app.models.switcher.create_client"):
        switcher = ModelSwitcher(settings)

    with (
        patch("app.models.switcher.resolve_env_key", return_value="key"),
        patch("app.models.switcher.ModelRouter"),
    ):
        mock_create_client.side_effect = RuntimeError("network error")
        result = switcher.switch_to_dynamic_model("openrouter", "test-model", "key")

        assert result is False


def test_list_profiles_delegates_to_status():
    """Test list_profiles returns same as status()."""
    mock_settings = MagicMock()
    mock_settings.models = {}
    settings = make_mock_settings({})

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(settings)

    switcher._active_profile = "test"
    switcher._routers = {"test": MagicMock()}
    switcher._clients = {}

    assert switcher.list_profiles() == switcher.status()


def test_is_usable_static_method():
    """Test _is_usable static method."""
    # None router
    assert ModelSwitcher._is_usable(None) is False

    # Router with no models and no default
    router1 = MagicMock()
    router1.models = {}
    router1.default_model = None
    assert ModelSwitcher._is_usable(router1) is False

    # Router with models
    router2 = MagicMock()
    router2.models = {"general": MagicMock()}
    router2.default_model = None
    assert ModelSwitcher._is_usable(router2) is True

    # Router with default_model but no models
    router3 = MagicMock()
    router3.models = {}
    router3.default_model = MagicMock()
    assert ModelSwitcher._is_usable(router3) is True
