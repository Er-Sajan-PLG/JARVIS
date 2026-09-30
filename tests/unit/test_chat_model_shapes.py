"""/api/chat must accept `model` as a dict OR a bare string.

Regression: the endpoint assumed ``model`` was always a dict and called
``.get()`` on it. Any caller sending a bare model id — the CLI, probes, and
hand-written curl requests all do — got HTTP 500
``'str' object has no attribute 'get'``.

Provider resolution must NOT be done by splitting on "/": catalogue ids are not
reliably "provider/model" ("x-ai/grok-4.20" is an *openrouter* model; agy ids
like "gemini-3.8-flash-high" have no slash at all). Splitting misroutes, or
falls through to the default and silently ignores the requested model.

These tests are hermetic. They drive the real route through
``fastapi.testclient.TestClient`` -- the same route ``app.main:app`` mounts --
and stub the one boundary that would leave the process: the model client the
handler creates at ``app/adapters/web/router.py`` ("client =
container.create_model_client(config)"). The catalogue lookup and the Settings
default are stubbed too, because both read ambient machine state (provider
network probes, the developer's ``settings.json``) that a gate must not depend
on. Every assertion here is about the REQUEST SHAPE -- did a bare string 500,
did a dict keep working, did an omitted model resolve the default -- so a stub
that returns a fixed ``ModelResponse`` is sufficient and honest.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.adapters.web import router as web_router_module
from app.models.client import ModelResponse

# The catalogue the handler consults to turn a bare model id into a provider.
# "nvidia/nemotron-3-super-120b-a12b" resolves to provider "nvidia"; the agy id
# has no slash at all, which is exactly why inference must not split on "/".
FAKE_CATALOGUE = {
    "providers": [
        {
            "key": "nvidia",
            "models": [{"id": "nvidia/nemotron-3-super-120b-a12b"}],
        },
        {
            "key": "agy",
            "models": [{"id": "gemini-3.8-flash-high"}],
        },
    ]
}

DEFAULT_PROVIDER = "nvidia"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"

# The provider spec the route asks for before building a ModelConfig. Pinned
# here so the test never calls the live provider registry (which probes
# provider HTTP endpoints for model lists).
FAKE_PROVIDER_SPEC = {
    "key": "nvidia",
    "api_endpoint": "https://example.invalid/v1",
    "requires_api_key": False,
}


class _StubModelClient:
    """A model client that records the config it was built from, then answers.

    Deliberately not a ``ModelClient`` subclass: that Protocol needs
    ``model_name``/``role`` properties this stub never uses, and duck typing is
    what the handler does (``_extract_content`` reads ``.content``).
    """

    def __init__(self, config) -> None:
        self.config = config

    def generate(self, messages, stream: bool = False, on_token=None, **kwargs) -> ModelResponse:
        return ModelResponse(content="stub response", model=self.config.name, tokens_used=3)


class _StubContainer:
    """Only the surface ``chat()`` touches, with the network edges removed."""

    def __init__(self) -> None:
        self.model_configs: list = []  # every config the route asked to run
        self.memory_service = AsyncMock()
        self.memory_service.search_memories.return_value = []

    def create_model_client(self, config):
        """THE SEAM. The real method builds a provider client and calls the LLM."""
        self.model_configs.append(config)
        return _StubModelClient(config)

    def get_provider_spec(self, provider: str):
        return FAKE_PROVIDER_SPEC


@pytest.fixture()
def container(monkeypatch: pytest.MonkeyPatch) -> _StubContainer:
    """Replace the composition root the route builds, and the catalogue it reads.

    ``bootstrap_system`` is looked up on the router module at call time, so
    patching it there covers the handler without importing or initialising the
    real container (no database, no data dir).
    """
    stub = _StubContainer()
    monkeypatch.setattr(web_router_module, "bootstrap_system", lambda *a, **k: stub)
    monkeypatch.setattr(
        web_router_module, "_build_catalogue", AsyncMock(return_value=FAKE_CATALOGUE)
    )
    return stub


@pytest.fixture()
def client(container: _StubContainer, api_key_env: str) -> TestClient:
    """The real app, with the credential the suite's ``api_key_env`` configured."""
    from app.main import app

    with TestClient(app) as c:
        c.headers["Authorization"] = f"Bearer {api_key_env}"
        yield c


def test_string_model_does_not_500(client: TestClient, container: _StubContainer) -> None:
    """The exact regression: a bare model id must not crash the endpoint."""
    response = client.post(
        "/api/chat",
        json={"message": "Say OK.", "model": "nvidia/nemotron-3-super-120b-a12b"},
    )
    assert (
        response.status_code == 200
    ), f"string model id returned {response.status_code}: {response.text}"
    assert response.json()["response"]
    # The catalogue resolved it -- nothing split the id on "/".
    assert container.model_configs[-1].backend == "nvidia"
    assert container.model_configs[-1].name == "nvidia/nemotron-3-super-120b-a12b"


def test_dict_model_still_works(client: TestClient, container: _StubContainer) -> None:
    """The original dict shape must keep working."""
    response = client.post(
        "/api/chat",
        json={
            "message": "Say OK.",
            "model": {"provider": "nvidia", "id": "nvidia/nemotron-3-super-120b-a12b"},
        },
    )
    assert (
        response.status_code == 200
    ), f"dict model returned {response.status_code}: {response.text}"
    assert container.model_configs[-1].backend == "nvidia"


def test_no_model_falls_back_to_settings_default(
    client: TestClient, container: _StubContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Omitting model must still resolve the Settings default.

    The default is injected rather than read, so the outcome does not depend on
    whichever model the machine running the gate happens to have saved.
    """
    from app.adapters.web import settings

    monkeypatch.setattr(
        settings,
        "get_default",
        lambda: {"provider": DEFAULT_PROVIDER, "model": DEFAULT_MODEL},
    )
    response = client.post("/api/chat", json={"message": "Say OK."})
    assert response.status_code == 200, response.text
    assert container.model_configs[-1].backend == DEFAULT_PROVIDER
    assert container.model_configs[-1].name == DEFAULT_MODEL


def test_chat_source_does_not_split_model_on_slash() -> None:
    """Guard the source: the slash-splitting inference must not come back."""
    src = (
        Path(__file__).resolve().parents[2] / "app" / "adapters" / "web" / "router.py"
    ).read_text()
    assert 'raw_model.split("/", 1)[0]' not in src, (
        "provider inference by string splitting is back — model ids are not "
        "'provider/model' (see module docstring)"
    )
    assert "isinstance(raw_model, str)" in src, "string model handling removed"
