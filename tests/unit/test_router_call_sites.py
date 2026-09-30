"""Guard: the model switcher stays off the abandoned ``ModelRouter``.

This file exists because it happened, twelve times, and nothing noticed.

``app/models/switcher.py`` and ``app/utils/model_selector.py`` called
``router.register(TaskType(role), client)`` and ``router.set_default(client)``
on a ``ModelRouter``. ``ModelRouter`` defines neither. Its entire public surface
is ``KEYWORDS``, ``classify_prompt``, ``generate``, ``register_provider`` and
``select_healthy_provider``; its only registration path needs a
``BaseLLMProvider``, and this tree contains **zero** implementations of that ABC.

The suite stayed green because every test replaced the class under test with a
mock. ``test_switcher.py`` patches ``ModelRouter`` in 33 places, so
``mock.set_default(...)`` was auto-created on first access and the tests asserted
against an interface that does not exist.

It was latent, not harmless. On a host with no Ollama-backed model,
``_build_default_local_router`` returned early and the app started normally.
Configure one and ``ModelSwitcher.__init__`` raised ``AttributeError`` -- caught
by a blanket ``except Exception`` that logged "Failed to build omni router" and
set ``_active_profile = ""``, so the switcher silently came up with no profiles.

The fix maps profiles straight to ``ModelClient``s. These tests hold that shape:
a static guard that the abandoned class does not come back, and behavioural
tests that a profile built from real configuration actually resolves.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.client import ModelClient
from app.models.switcher import ModelSwitcher

REPO_ROOT = Path(__file__).resolve().parents[2]
ABANDONED_CLASS = "ModelRouter"

# The two modules that used to drive ModelRouter. Pinned by name so a rename
# cannot silently drop them from scope.
GUARDED_MODULES = ("app/models/switcher.py", "app/utils/model_selector.py")


def _builds_abandoned_class(path: Path) -> list[int]:
    """Line numbers where `ModelRouter(...)` is called."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == ABANDONED_CLASS
        ):
            lines.append(node.lineno)
    return lines


@pytest.mark.parametrize("rel", GUARDED_MODULES)
def test_switcher_does_not_construct_the_abandoned_router(rel: str) -> None:
    """ModelRouter must not be built here: it cannot be registered into.

    ``register_provider`` requires a ``BaseLLMProvider``. Nothing in ``app/``
    subclasses it, so any ``ModelRouter`` built in these modules is guaranteed
    inert, and driving it raised AttributeError on top of that.
    """
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} moved; update GUARDED_MODULES"
    lines = _builds_abandoned_class(path)
    assert lines == [], (
        f"{rel} constructs {ABANDONED_CLASS} at line(s) {lines}. That class has no "
        f"BaseLLMProvider implementations to register, and no register/set_default "
        f"method. Map the profile to a ModelClient instead."
    )


def _stub_client(model_name: str, role: str) -> MagicMock:
    """A stand-in that satisfies ModelClient's shape."""
    client = MagicMock(spec=ModelClient)
    client.model_name = model_name
    client.role = role
    return client


def _make_settings(models: dict) -> MagicMock:
    settings = MagicMock()
    settings.models = models
    settings.active_profile = ""
    return settings


def _make_config(backend: str, name: str, role: str = "general") -> MagicMock:
    cfg = MagicMock()
    cfg.backend = backend
    cfg.name = name
    cfg.role = role
    return cfg


@pytest.mark.parametrize(
    "models",
    [
        {"cloud": _make_config("openrouter", "some/cloud-model")},
        {"local": _make_config("ollama", "llama3.1:8b")},
        {
            "cloud": _make_config("openrouter", "some/cloud-model"),
            "local": _make_config("ollama", "llama3.1:8b"),
        },
    ],
    ids=["cloud-only", "ollama-only", "both"],
)
def test_a_real_switcher_always_ends_up_with_a_usable_profile(models: dict) -> None:
    """Behavioural: construction yields a profile that resolves to a client.

    Every parametrisation here reaches the code that used to raise. With an
    ollama model configured, ``_build_default_local_router`` no longer returns
    early, so the old ``router.register(...)``/``set_default(...)`` ran and threw
    -- and the blanket ``except Exception`` in ``__init__`` turned that into a
    silent ``_active_profile = ""``. Asserting a *non-empty* profile is the part
    that would have failed.
    """
    with patch("app.models.switcher.create_client") as create:
        create.side_effect = lambda cfg: _stub_client(cfg.name, cfg.role)
        switcher = ModelSwitcher(_make_settings(models))

    assert switcher.active_profile != "", (
        "the switcher came up with no active profile -- the silent-degradation "
        "path that masked the AttributeError"
    )
    active = switcher.router
    assert isinstance(active, ModelClient), f"active profile yielded {type(active)}"
    assert callable(active.generate)


def test_the_ollama_profile_is_preferred_as_default() -> None:
    """The "default" profile picks the Ollama client when one is configured."""
    models = {
        "cloud": _make_config("openrouter", "some/cloud-model"),
        "local": _make_config("ollama", "llama3.1:8b"),
    }
    with patch("app.models.switcher.create_client") as create:
        create.side_effect = lambda cfg: _stub_client(cfg.name, cfg.role)
        switcher = ModelSwitcher(_make_settings(models))

    assert switcher.active_profile == "default"
    assert switcher.router.model_name == "llama3.1:8b"


def test_switch_to_model_makes_that_model_active() -> None:
    """`switch_to_model` must return True and actually change the active client.

    This is the user-facing path that raised AttributeError: it built a
    ModelRouter and registered into it before touching ``_active_profile``.
    """
    models = {"cloud": _make_config("openrouter", "some/cloud-model")}
    with patch("app.models.switcher.create_client") as create:
        create.side_effect = lambda cfg: _stub_client(cfg.name, cfg.role)
        switcher = ModelSwitcher(_make_settings(models))

    assert switcher.switch_to_model("cloud") is True
    assert switcher.active_profile == "model:cloud"
    assert switcher.router.model_name == "some/cloud-model"


def test_switch_to_model_rejects_an_unknown_key() -> None:
    """Negative control: an unloaded model must not become active."""
    with patch("app.models.switcher.create_client") as create:
        create.side_effect = lambda cfg: _stub_client(cfg.name, cfg.role)
        switcher = ModelSwitcher(_make_settings({"cloud": _make_config("openrouter", "m")}))

    assert switcher.switch_to_model("nope") is False
    assert switcher.active_profile != "model:nope"


def test_switch_rejects_a_profile_whose_client_cannot_generate() -> None:
    """`_is_usable` must judge the client, not a MagicMock's auto-attributes.

    It previously read ``router.default_model`` -- absent on the real
    ``ModelRouter``, auto-created on a mock. A client without ``generate`` is the
    honest way to express "this profile cannot serve requests".
    """
    with patch("app.models.switcher.create_client") as create:
        create.side_effect = lambda cfg: _stub_client(cfg.name, cfg.role)
        switcher = ModelSwitcher(_make_settings({"cloud": _make_config("openrouter", "m")}))

    switcher._routers["broken"] = object()  # type: ignore[assignment]
    assert switcher.switch("broken") is False
