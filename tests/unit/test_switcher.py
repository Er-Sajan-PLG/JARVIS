"""Unit tests for app/models/switcher.py, read through the switcher's own state.

``ModelSwitcher`` used to build ``ModelRouter`` objects and call
``router.register(...)`` / ``router.set_default(...)``. Neither method exists on
that class, and its only registration path needs a ``BaseLLMProvider`` of which
this tree has none -- so every one of those calls raised ``AttributeError``,
inside a blanket ``except Exception`` that degraded the switcher to no active
profile. The suite stayed green because it patched ``ModelRouter`` and asserted
against the interface a ``MagicMock`` auto-creates.

Nothing here patches a router. A profile is a name mapped to a ``ModelClient``,
so these tests assert what a caller can observe: ``active_profile``, ``router``,
``get_client``, ``switch``, ``switch_to_model``, ``status`` -- and ``_routers``
where the profile -> client mapping is itself the subject.
``tests/unit/test_router_call_sites.py`` is the static half of the same guard.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.models.client import ModelClient
from app.models.omni_client import OmniModelClient
from app.models.switcher import ModelSwitcher


def _stub_client(model_name: str = "test-model", role: str = "general") -> MagicMock:
    """A stand-in that actually satisfies the ModelClient protocol."""
    client = MagicMock(spec=ModelClient)
    client.model_name = model_name
    client.role = role
    return client


def _make_settings(models: dict) -> MagicMock:
    settings = MagicMock()
    settings.models = models
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


def _recording_create_client() -> tuple[dict[str, MagicMock], Callable[[MagicMock], MagicMock]]:
    """A ``create_client`` double returning one stub per config, kept by name."""
    built: dict[str, MagicMock] = {}

    def _create(cfg: MagicMock) -> MagicMock:
        built[cfg.name] = _stub_client(cfg.name, cfg.role)
        return built[cfg.name]

    return built, _create


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #


def test_switcher_init_creates_clients() -> None:
    """__init__ builds one client per configured model, keyed by config key."""
    configs = {
        "model1": _make_config("model1", "ollama", "Llama-3-8B"),
        "model2": _make_config("model2", "google", "Gemini-Pro", role="code"),
    }
    built, create = _recording_create_client()
    settings = _make_settings(configs)

    with patch("app.models.switcher.create_client", side_effect=create) as create_client:
        switcher = ModelSwitcher(settings)

    assert create_client.call_count == 2
    assert switcher.get_client("model1") is built["Llama-3-8B"]
    assert switcher.get_client("model2") is built["Gemini-Pro"]
    assert isinstance(switcher.get_client("model1"), ModelClient)


def test_switcher_init_skips_failed_clients(caplog) -> None:
    """A model whose client cannot be built is logged and skipped, not fatal."""
    good = _stub_client("Good-Model")

    def _create(cfg: MagicMock) -> MagicMock:
        if cfg.name == "bad":
            raise RuntimeError("API key missing")
        return good

    settings = _make_settings({"good": _make_config("good"), "bad": _make_config("bad")})

    with patch("app.models.switcher.create_client", side_effect=_create):
        switcher = ModelSwitcher(settings)

    assert switcher.get_client("good") is good
    assert switcher.get_client("bad") is None
    assert "Could not load 'bad'" in caplog.text


def test_switcher_init_treats_a_client_whose_role_accessor_raises_as_general(caplog) -> None:
    """A raising ``role`` accessor must not take construction down.

    ``getattr(client, "role", None)`` does not cover this: its default applies to
    a *missing* attribute, not to one whose accessor raises. Unguarded, the raise
    propagates out of ``__init__`` and the switcher never comes up.
    """

    class RaisingRoleClient(MagicMock):
        @property
        def role(self):
            raise RuntimeError("role access failure")

    client = RaisingRoleClient()
    client.model_name = "ProblemClient"
    settings = _make_settings({"p1": _make_config("p1", backend="other")})

    with patch("app.models.switcher.create_client", return_value=client):
        switcher = ModelSwitcher(settings)

    assert switcher.active_profile == "omni"
    assert "raised on .role" in caplog.text


def test_switcher_init_prefers_the_default_profile_over_omni() -> None:
    """An Ollama model makes "default" active; both profiles are still built."""
    built, create = _recording_create_client()
    configs = {
        "cloud": _make_config("cloud", "openrouter", "some/cloud-model"),
        "local": _make_config("local", "ollama", "Small-1.5B"),
    }

    with patch("app.models.switcher.create_client", side_effect=create):
        switcher = ModelSwitcher(_make_settings(configs))

    assert set(switcher._routers) == {"omni", "default"}
    assert switcher.active_profile == "default"
    assert switcher.router is built["Small-1.5B"]


def test_switcher_init_honours_a_requested_usable_profile() -> None:
    """A configured active_profile wins over the built-in default preference."""
    configs = {
        "cloud": _make_config("cloud", "openrouter", "some/cloud-model"),
        "local": _make_config("local", "ollama", "Small-1.5B"),
    }
    settings = _make_settings(configs)
    settings.active_profile = "omni"

    with patch(
        "app.models.switcher.create_client",
        side_effect=lambda cfg: _stub_client(cfg.name, cfg.role),
    ):
        switcher = ModelSwitcher(settings)

    assert switcher.active_profile == "omni"
    assert isinstance(switcher.router, OmniModelClient)


def test_switcher_init_ignores_a_requested_profile_that_was_not_built() -> None:
    """A requested profile that does not exist falls back to "default"."""
    settings = _make_settings({"local": _make_config("local", "ollama", "Small-1.5B")})
    settings.active_profile = "nonexistent"

    with patch(
        "app.models.switcher.create_client",
        side_effect=lambda cfg: _stub_client(cfg.name, cfg.role),
    ):
        switcher = ModelSwitcher(settings)

    assert switcher.active_profile == "default"


def test_switcher_init_falls_back_to_the_first_profile_when_no_named_profile_exists() -> None:
    """The last-resort branch: any profile at all beats no active profile.

    No plain construction reaches it -- "omni" is built whenever any client
    loaded and "default" whenever an Ollama model did -- so the branch is pinned
    by injecting a profile the way ``_build_ollama_router`` does at startup.
    """

    def _inject(switcher_self: ModelSwitcher, settings: MagicMock) -> None:
        switcher_self._routers["custom_pool"] = _stub_client("Pooled")
        return None

    settings = _make_settings({})
    settings.active_profile = "missing"

    with patch.object(ModelSwitcher, "_build_default_local_router", _inject):
        switcher = ModelSwitcher(settings)

    assert switcher.active_profile == "custom_pool"


# --------------------------------------------------------------------------- #
# Model-size parsing (drives which local model "default" picks)
# --------------------------------------------------------------------------- #


def test_ollama_model_size_parses_correctly() -> None:
    """_ollama_model_size extracts the parameter count from the model name."""
    switcher = ModelSwitcher(_make_settings({}))

    assert switcher._ollama_model_size("Llama-3-8B") == 8.0
    assert switcher._ollama_model_size("Model-7B-v2") == 7.0
    assert switcher._ollama_model_size("Small-1.5B") == 1.5
    assert switcher._ollama_model_size("Huge-70B") == 70.0


def test_ollama_model_size_handles_unknown_format() -> None:
    """An unparseable name sorts last, and a non-string never raises."""
    switcher = ModelSwitcher(_make_settings({}))

    assert switcher._ollama_model_size("no-size-here") == float("inf")
    assert switcher._ollama_model_size("") == float("inf")
    assert switcher._ollama_model_size("test") == float("inf")
    assert switcher._ollama_model_size(123) == float("inf")


def test_ollama_model_size_additional_units() -> None:
    """'k', 'm' and 'g' units are normalised onto the same B-based scale."""
    switcher = ModelSwitcher(_make_settings({}))

    assert switcher._ollama_model_size("model-500k") == 0.5
    assert switcher._ollama_model_size("model-350m") == 350.0
    assert switcher._ollama_model_size("model-2g") == 2000.0


def test_build_default_local_router_selects_smallest_ollama() -> None:
    """The "default" profile resolves to the smallest local Ollama client."""
    configs = {
        "m_large": _make_config("m_large", "ollama", "Model-8B"),
        "m_small": _make_config("m_small", "ollama", "Model-1.5B"),
        "m_non_ollama": _make_config("m_non_ollama", "google", "Gemini"),
    }
    built, create = _recording_create_client()
    settings = _make_settings(configs)

    with patch("app.models.switcher.create_client", side_effect=create):
        switcher = ModelSwitcher(settings)

    assert switcher._build_default_local_router(settings) is built["Model-1.5B"]
    assert switcher._routers["default"] is built["Model-1.5B"]
    assert switcher._routers["default"] is not built["Gemini"]
    assert switcher.router is built["Model-1.5B"]


def test_build_default_local_router_returns_none_when_no_ollama() -> None:
    """With no Ollama model configured there is no "default" profile."""
    _, create = _recording_create_client()
    settings = _make_settings({"cloud": _make_config("cloud", "google", "Gemini")})

    with patch("app.models.switcher.create_client", side_effect=create):
        switcher = ModelSwitcher(settings)

    assert switcher._build_default_local_router(settings) is None
    assert "default" not in switcher._routers
    assert switcher.active_profile == "omni"


# --------------------------------------------------------------------------- #
# switch() / router / active_profile / get_client
# --------------------------------------------------------------------------- #


def test_switch_returns_false_for_unknown_profile() -> None:
    """switch() refuses a profile that was never built."""
    switcher = ModelSwitcher(_make_settings({}))

    assert switcher.switch("nonexistent") is False
    assert switcher.active_profile == ""


@pytest.mark.parametrize(
    "unusable",
    [None, MagicMock(spec=[]), SimpleNamespace(generate="not callable")],
    ids=["no-client", "client-without-generate", "generate-is-not-callable"],
)
def test_switch_returns_false_for_an_unusable_profile(unusable: object) -> None:
    """switch() refuses a profile whose client cannot generate.

    ``_is_usable`` judges the client's ``generate``; it used to read
    ``router.default_model``, which the real ``ModelRouter`` never had and a
    ``MagicMock`` always answers.
    """
    switcher = ModelSwitcher(_make_settings({}))
    switcher._routers["broken"] = unusable  # type: ignore[assignment]

    assert switcher.switch("broken") is False
    assert switcher.active_profile == ""


def test_switch_returns_true_and_sets_active_for_usable() -> None:
    """switch() moves the active profile to a usable one it was given."""
    configs = {
        "cloud": _make_config("cloud", "openrouter", "some/cloud-model"),
        "local": _make_config("local", "ollama", "Small-1.5B"),
    }

    with patch(
        "app.models.switcher.create_client",
        side_effect=lambda cfg: _stub_client(cfg.name, cfg.role),
    ):
        switcher = ModelSwitcher(_make_settings(configs))

    assert switcher.active_profile == "default"

    assert switcher.switch("omni") is True
    assert switcher.active_profile == "omni"
    assert isinstance(switcher.router, OmniModelClient)
    assert callable(switcher.router.generate)


def test_router_property_returns_the_active_client() -> None:
    """``router`` is the client the active profile selects, not a ModelRouter."""
    built, create = _recording_create_client()
    settings = _make_settings({"cloud": _make_config("cloud", "openrouter", "some/cloud-model")})

    with patch("app.models.switcher.create_client", side_effect=create):
        switcher = ModelSwitcher(settings)

    assert switcher.switch_to_model("cloud") is True

    active = switcher.router
    assert active is built["some/cloud-model"]
    assert isinstance(active, ModelClient)
    assert callable(active.generate)


def test_active_profile_property_tracks_the_switch() -> None:
    """``active_profile`` follows whatever switch() last accepted."""
    configs = {
        "cloud": _make_config("cloud", "openrouter", "some/cloud-model"),
        "local": _make_config("local", "ollama", "Small-1.5B"),
    }

    with patch(
        "app.models.switcher.create_client",
        side_effect=lambda cfg: _stub_client(cfg.name, cfg.role),
    ):
        switcher = ModelSwitcher(_make_settings(configs))

    assert switcher.active_profile == "default"

    assert switcher.switch("omni") is True
    assert switcher.active_profile == "omni"


def test_get_client_returns_loaded_client() -> None:
    """get_client() returns the loaded client for a key, None when absent."""
    built, create = _recording_create_client()
    settings = _make_settings({"model1": _make_config("model1", "ollama", "Small-1.5B")})

    with patch("app.models.switcher.create_client", side_effect=create):
        switcher = ModelSwitcher(settings)

    assert switcher.get_client("model1") is built["Small-1.5B"]
    assert switcher.get_client("missing") is None


def test_status_formats_output() -> None:
    """status() reports the active profile, the profiles, and the loaded models."""
    configs = {
        "local": _make_config("local", "ollama", "Small-1.5B"),
        "cloud": _make_config("cloud", "google", "Gemini-Pro", role="code"),
    }

    with patch(
        "app.models.switcher.create_client",
        side_effect=lambda cfg: _stub_client(cfg.name, cfg.role),
    ):
        switcher = ModelSwitcher(_make_settings(configs))

    status = switcher.status()

    assert "Active profile: default" in status
    assert "Available profiles:" in status
    assert "  ○ omni" in status
    assert "  ● default" in status
    assert "Loaded models:" in status
    assert "  local: Small-1.5B (general)" in status
    assert "  cloud: Gemini-Pro (code)" in status


def test_list_profiles_delegates_to_status() -> None:
    """list_profiles() is status(), and carries its content."""
    with patch(
        "app.models.switcher.create_client",
        side_effect=lambda cfg: _stub_client(cfg.name, cfg.role),
    ):
        switcher = ModelSwitcher(
            _make_settings({"cloud": _make_config("cloud", "openrouter", "some/cloud-model")})
        )

    assert switcher.list_profiles() == switcher.status()
    assert "Active profile: omni" in switcher.list_profiles()


def test_is_usable_returns_true_only_for_a_client_that_can_generate() -> None:
    """_is_usable judges the client, which is what a profile now holds."""
    assert ModelSwitcher._is_usable(None) is False
    assert ModelSwitcher._is_usable(_stub_client()) is True
    assert ModelSwitcher._is_usable(MagicMock(spec=[])) is False
    assert ModelSwitcher._is_usable(SimpleNamespace(generate="not callable")) is False


# --------------------------------------------------------------------------- #
# switch_to_model / switch_to_dynamic_model
# --------------------------------------------------------------------------- #


def test_switch_to_model_success() -> None:
    """switch_to_model() maps a "model:<key>" profile straight to that client."""
    built, create = _recording_create_client()
    settings = _make_settings({"my_model": _make_config("my_model", "ollama", "Llama-3-8B")})

    with patch("app.models.switcher.create_client", side_effect=create):
        switcher = ModelSwitcher(settings)

    assert switcher.switch_to_model("my_model") is True
    assert switcher.active_profile == "model:my_model"
    assert switcher._routers["model:my_model"] is built["Llama-3-8B"]
    assert switcher.router is built["Llama-3-8B"]


def test_switch_to_model_returns_false_for_missing_client() -> None:
    """A model that never loaded must not become an active profile."""
    with patch(
        "app.models.switcher.create_client",
        side_effect=lambda cfg: _stub_client(cfg.name, cfg.role),
    ):
        switcher = ModelSwitcher(
            _make_settings({"cloud": _make_config("cloud", "openrouter", "some/cloud-model")})
        )

    assert switcher.switch_to_model("missing_key") is False
    assert "model:missing_key" not in switcher._routers
    assert switcher.active_profile == "omni"


def test_switch_to_dynamic_model_with_a_direct_key_activates_the_client() -> None:
    """A direct key is used verbatim and the built client becomes active."""
    switcher = ModelSwitcher(_make_settings({}))
    dynamic = _stub_client("deepseek/deepseek-r1")

    with patch("app.models.switcher.create_client", return_value=dynamic) as create_client:
        result = switcher.switch_to_dynamic_model("openrouter", "deepseek/deepseek-r1", "sk-direct")

    assert result is True
    key = "dyn:openrouter:deepseek/deepseek-r1"
    assert switcher.active_profile == key
    assert switcher._routers[key] is dynamic
    assert switcher.router is dynamic
    assert isinstance(dynamic, ModelClient)

    cfg = create_client.call_args.args[0]
    assert cfg.name == "deepseek/deepseek-r1"
    assert cfg.backend == "openrouter"
    assert cfg.role == "general"
    assert cfg.api_key == "sk-direct"


def test_switch_to_dynamic_model_with_an_env_reference_reads_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``env:VAR`` is resolved through the environment, not sent as the key."""
    monkeypatch.setenv("JARVIS_DYNAMIC_TEST_KEY", "sk-from-env")
    switcher = ModelSwitcher(_make_settings({}))
    dynamic = _stub_client("deepseek/deepseek-r1")

    with patch("app.models.switcher.create_client", return_value=dynamic) as create_client:
        result = switcher.switch_to_dynamic_model(
            "openrouter", "deepseek/deepseek-r1", "env:JARVIS_DYNAMIC_TEST_KEY"
        )

    assert result is True
    assert create_client.call_args.args[0].api_key == "sk-from-env"
    assert switcher.router is dynamic


def test_switch_to_dynamic_model_returns_false_when_the_env_var_is_missing(
    monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    """An unset ``env:VAR`` fails closed: nothing built, nothing activated."""
    monkeypatch.delenv("JARVIS_DYNAMIC_ABSENT_KEY", raising=False)
    switcher = ModelSwitcher(_make_settings({}))

    with patch("app.models.switcher.create_client") as create_client:
        result = switcher.switch_to_dynamic_model(
            "openrouter", "test-model", "env:JARVIS_DYNAMIC_ABSENT_KEY"
        )

    assert result is False
    create_client.assert_not_called()
    assert switcher.active_profile == ""
    assert [key for key in switcher._routers if key.startswith("dyn:")] == []
    assert "JARVIS_DYNAMIC_ABSENT_KEY" in caplog.text


def test_switch_to_dynamic_model_returns_false_on_create_error(caplog) -> None:
    """A client that cannot be built leaves the switcher untouched."""
    switcher = ModelSwitcher(_make_settings({}))

    with patch("app.models.switcher.create_client", side_effect=RuntimeError("network error")):
        result = switcher.switch_to_dynamic_model("openrouter", "test-model", "sk-direct")

    assert result is False
    assert switcher.active_profile == ""
    assert [key for key in switcher._routers if key.startswith("dyn:")] == []
    assert "Could not build dynamic openrouter client" in caplog.text
