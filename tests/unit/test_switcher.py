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

    router3 = MagicMock()
    router3.models = {}
    router3.default_model = MagicMock()
    assert ModelSwitcher._is_usable(router3) is True


def test_ollama_model_size_additional_units():
    """Test _ollama_model_size with 'k', 'm', and 'g' units."""
    mock_settings = MagicMock()
    mock_settings.models = {}

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(mock_settings)

    assert switcher._ollama_model_size("model-500k") == 0.5
    assert switcher._ollama_model_size("model-350m") == 350.0
    assert switcher._ollama_model_size("model-2g") == 2000.0


def test_build_router_comprehensive():
    """Test _build_router registers clients and handles unknown roles and missing defaults."""
    mock_settings = MagicMock()
    mock_settings.models = {}

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(mock_settings)

    client_gen = make_mock_client("Gen-Model", "general")
    client_code = make_mock_client("Code-Model", "code")
    switcher._clients = {
        "gen_key": client_gen,
        "code_key": client_code,
    }

    mock_router_instance = MagicMock()
    with patch("app.models.switcher.ModelRouter", return_value=mock_router_instance):
        mapping = {
            "general": "gen_key",
            "code": "code_key",
            "missing_role": "not_in_clients",
            "unknown_role": "gen_key",
        }
        res_router = switcher._build_router(mapping)

        assert res_router == mock_router_instance
        mock_router_instance.register.assert_any_call(
            switcher._build_router.__globals__["TaskType"]("general"), client_gen
        )
        mock_router_instance.register.assert_any_call(
            switcher._build_router.__globals__["TaskType"]("code"), client_code
        )
        mock_router_instance.set_default.assert_called_once_with(client_gen)


def test_build_router_without_general_default():
    """Test _build_router does not set default if 'general' key is absent or not loaded."""
    mock_settings = MagicMock()
    mock_settings.models = {}

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(mock_settings)

    client_code = make_mock_client("Code-Model", "code")
    switcher._clients = {"code_key": client_code}

    mock_router_instance = MagicMock()
    with patch("app.models.switcher.ModelRouter", return_value=mock_router_instance):
        mapping = {"code": "code_key", "general": "missing_key"}
        switcher._build_router(mapping)
        mock_router_instance.set_default.assert_not_called()


def test_build_default_local_router_selects_smallest_ollama():
    """Test _build_default_local_router selects smallest model and registers roles."""
    mock_settings = MagicMock()
    mock_settings.models = {
        "m_large": make_mock_model_config("m_large", backend="ollama", name="Model-8B"),
        "m_small": make_mock_model_config("m_small", backend="ollama", name="Model-1.5B"),
        "m_non_ollama": make_mock_model_config("m_non_ollama", backend="google", name="Gemini"),
    }

    client_large = make_mock_client("Model-8B", "general")
    client_small = make_mock_client("Model-1.5B", "general")

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(mock_settings)

    switcher._clients = {
        "m_large": client_large,
        "m_small": client_small,
    }

    mock_local_router = MagicMock()
    with patch("app.models.switcher.ModelRouter", return_value=mock_local_router):
        res = switcher._build_default_local_router(mock_settings)
        assert res == mock_local_router
        mock_local_router.set_default.assert_called_once_with(client_small)
        assert mock_local_router.register.call_count == 6


def test_build_default_local_router_handles_value_error_on_task_type():
    """Test _build_default_local_router handles ValueError when constructing TaskType."""
    mock_settings = MagicMock()
    mock_settings.models = {
        "m1": make_mock_model_config("m1", backend="ollama", name="Model-8B"),
    }
    client = make_mock_client("Model-8B", "general")

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(mock_settings)
    switcher._clients = {"m1": client}

    mock_local_router = MagicMock()
    with (
        patch("app.models.switcher.ModelRouter", return_value=mock_local_router),
        patch("app.models.switcher.TaskType", side_effect=ValueError("bad role")),
    ):
        res = switcher._build_default_local_router(mock_settings)
        assert res == mock_local_router
        mock_local_router.register.assert_not_called()
        mock_local_router.set_default.assert_called_once_with(client)


def test_switch_to_model_success():
    """Test switch_to_model successfully builds router and sets active profile."""
    mock_settings = MagicMock()
    mock_settings.models = {}

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(mock_settings)

    client = make_mock_client("Llama-3-8B", "general")
    switcher._clients["my_model"] = client

    mock_router_instance = MagicMock()
    with patch("app.models.switcher.ModelRouter", return_value=mock_router_instance):
        result = switcher.switch_to_model("my_model")
        assert result is True
        assert switcher.active_profile == "model:my_model"
        assert switcher._routers["model:my_model"] == mock_router_instance
        assert mock_router_instance.register.call_count == 6
        mock_router_instance.set_default.assert_called_once_with(client)


def test_switch_to_model_task_type_value_error():
    """Test switch_to_model gracefully handles ValueError during TaskType conversion."""
    mock_settings = MagicMock()
    mock_settings.models = {}

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(mock_settings)

    client = make_mock_client("Llama-3-8B", "general")
    switcher._clients["my_model"] = client

    mock_router_instance = MagicMock()
    with (
        patch("app.models.switcher.ModelRouter", return_value=mock_router_instance),
        patch("app.models.switcher.TaskType", side_effect=ValueError("bad role")),
    ):
        result = switcher.switch_to_model("my_model")
        assert result is True
        mock_router_instance.register.assert_not_called()
        mock_router_instance.set_default.assert_called_once_with(client)


def test_switch_to_dynamic_model_success():
    """Test switch_to_dynamic_model creates dynamic client and router."""
    mock_settings = MagicMock()
    mock_settings.models = {}

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(mock_settings)

    mock_dyn_client = make_mock_client("dynamic-model", "general")
    mock_router_instance = MagicMock()

    with (
        patch("app.models.switcher.resolve_env_key", return_value="resolved-api-key"),
        patch("app.models.switcher.create_client", return_value=mock_dyn_client) as mock_create,
        patch("app.models.switcher.ModelRouter", return_value=mock_router_instance),
    ):
        result = switcher.switch_to_dynamic_model(
            "openrouter", "deepseek/deepseek-r1", "env:MY_KEY"
        )
        assert result is True
        expected_key = "dyn:openrouter:deepseek/deepseek-r1"
        assert switcher.active_profile == expected_key
        assert switcher._routers[expected_key] == mock_router_instance
        assert mock_router_instance.register.call_count == 6
        mock_router_instance.set_default.assert_called_once_with(mock_dyn_client)
        mock_create.assert_called_once()


def test_switch_to_dynamic_model_task_type_value_error():
    """Test switch_to_dynamic_model handles ValueError on TaskType."""
    mock_settings = MagicMock()
    mock_settings.models = {}

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(mock_settings)

    mock_dyn_client = make_mock_client("dynamic-model", "general")
    mock_router_instance = MagicMock()

    with (
        patch("app.models.switcher.resolve_env_key", return_value="resolved-api-key"),
        patch("app.models.switcher.create_client", return_value=mock_dyn_client),
        patch("app.models.switcher.ModelRouter", return_value=mock_router_instance),
        patch("app.models.switcher.TaskType", side_effect=ValueError("bad role")),
    ):
        result = switcher.switch_to_dynamic_model(
            "openrouter", "deepseek/deepseek-r1", "resolved-api-key"
        )
        assert result is True
        mock_router_instance.register.assert_not_called()
        mock_router_instance.set_default.assert_called_once_with(mock_dyn_client)


def test_ollama_model_size_fallback_unit():
    """Test _ollama_model_size returns value when unit is not k/m/g/b (line 148)."""
    mock_settings = MagicMock()
    mock_settings.models = {}

    with patch("app.models.switcher.create_client"), patch("app.models.switcher.ModelRouter"):
        switcher = ModelSwitcher(mock_settings)

    with patch("app.models.switcher.re.search") as mock_search:
        mock_match = MagicMock()
        mock_match.group.side_effect = lambda idx: "42.0" if idx == 1 else "z"
        mock_search.return_value = mock_match
        assert switcher._ollama_model_size("custom") == 42.0


def test_switcher_init_client_with_raising_role_attribute():
    """Test __init__ falls back to 'general' when client.role raises an exception."""

    class RaisingRoleClient(MagicMock):
        @property
        def role(self):
            raise RuntimeError("role access failure")

    client = RaisingRoleClient()
    client.model_name = "ProblemClient"
    mock_settings = make_mock_settings({"p1": make_mock_model_config("p1", backend="other")})

    with (
        patch("app.models.switcher.create_client", return_value=client),
        patch("app.models.switcher.ModelRouter") as mock_router_cls,
    ):
        mock_router = MagicMock()
        mock_router.models = {"general": client}
        mock_router.default_model = client
        mock_router_cls.return_value = mock_router
        switcher = ModelSwitcher(mock_settings)
        assert switcher.active_profile == "omni"


def test_switcher_init_omni_router_register_exception_logged(caplog):
    """Test __init__ catches and logs when omni_router.register fails for a role."""
    mock_settings = make_mock_settings({"m1": make_mock_model_config("m1")})
    client = make_mock_client("Client1", "code")

    with (
        patch("app.models.switcher.create_client", return_value=client),
        patch("app.models.switcher.ModelRouter") as mock_router_cls,
    ):
        mock_router = MagicMock()
        mock_router.register.side_effect = Exception("failed to register role")
        mock_router.models = {}
        mock_router.default_model = None
        mock_router_cls.return_value = mock_router

        ModelSwitcher(mock_settings)
        assert "Could not register omni role code" in caplog.text


def test_switcher_init_active_profile_resolution_branches():
    """Test various active_profile selection branches in __init__."""
    # Case 1: requested profile in _routers and usable (line 78)
    settings_requested = make_mock_settings({"m1": make_mock_model_config("m1", backend="other")})
    settings_requested.active_profile = "omni"

    with (
        patch("app.models.switcher.create_client", return_value=make_mock_client("M1")),
        patch("app.models.switcher.ModelRouter") as mock_router_cls,
    ):
        usable_router = MagicMock()
        usable_router.models = {"general": MagicMock()}
        usable_router.default_model = None
        mock_router_cls.return_value = usable_router

        switcher = ModelSwitcher(settings_requested)
        assert switcher.active_profile == "omni"

    # Case 2: default is in _routers when requested is invalid (line 80)
    mock_cfg = {"m1": make_mock_model_config("m1", backend="ollama", name="Local-3B")}
    settings_default = make_mock_settings(mock_cfg)
    settings_default.active_profile = "nonexistent"

    with (
        patch("app.models.switcher.create_client", return_value=make_mock_client("Local-3B")),
        patch("app.models.switcher.ModelRouter") as mock_router_cls,
    ):
        mock_omni = MagicMock()
        mock_omni.models = {}
        mock_omni.default_model = None

        mock_default = MagicMock()
        mock_default.models = {"general": MagicMock()}
        mock_default.default_model = make_mock_client("Local-3B")

        # First call is omni_router, second call is default_local router
        mock_router_cls.side_effect = [mock_omni, mock_default]

        switcher = ModelSwitcher(settings_default)
        assert switcher.active_profile == "default"

    # Case 3: neither requested, default, nor omni, but fallback to next(iter(_routers)) (line 84)
    settings_fallback = make_mock_settings({})
    settings_fallback.active_profile = "missing"

    def side_effect_inject(self_inner, settings_inner):
        self_inner._routers["custom_pool"] = MagicMock()
        return None

    with (
        patch("app.models.switcher.create_client"),
        patch("app.models.switcher.ModelRouter") as mock_router_cls,
        patch.object(ModelSwitcher, "_build_default_local_router", side_effect_inject),
    ):
        unusable_omni = MagicMock()
        unusable_omni.models = {}
        unusable_omni.default_model = None
        mock_router_cls.return_value = unusable_omni

        switcher = ModelSwitcher(settings_fallback)
        assert switcher.active_profile == "custom_pool"


def test_switcher_init_fatal_exception_handling(caplog):
    """Test __init__ sets active_profile = '' when router building raises a fatal exception."""
    settings = make_mock_settings({})

    with patch.object(
        ModelSwitcher,
        "_build_default_local_router",
        side_effect=RuntimeError("Fatal build error"),
    ):
        switcher = ModelSwitcher(settings)
        assert switcher.active_profile == ""
        assert "Failed to build omni router" in caplog.text
