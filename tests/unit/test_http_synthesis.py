"""Tests for HTTP-path answer synthesis (Migration Plan Step 5).

The contract being protected: with ``JARVIS_HTTP_LLM`` off, the REST response is
byte-for-byte what it has always been. Every existing HITL consumer depends on
that, so the flag's default matters more than the feature it enables.
"""

from __future__ import annotations

import pytest

from app.adapters.http import synthesis


class _FakeMemoryRecord:
    def __init__(self, value: str) -> None:
        self.value = value


class _FakeMemoryService:
    """Records stores; returns canned recall."""

    def __init__(self, memories: list[str] | None = None, fail_recall: bool = False) -> None:
        self._memories = memories or []
        self._fail_recall = fail_recall
        self.stored: list[tuple[str, str]] = []

    async def search_memories(self, query: str, limit: int = 5) -> list[_FakeMemoryRecord]:
        if self._fail_recall:
            raise RuntimeError("vector store unavailable")
        return [_FakeMemoryRecord(m) for m in self._memories[:limit]]

    async def store_memory(self, key: str, value: str, category: str = "general") -> None:
        self.stored.append((key, value))


class _FakeClient:
    def __init__(self, content: str = "synthesized answer", fail: bool = False) -> None:
        self._content = content
        self._fail = fail
        self.prompts: list[list[dict]] = []

    def generate(self, messages: list[dict]) -> tuple[str, int]:
        self.prompts.append(messages)
        if self._fail:
            raise RuntimeError("provider 503")
        return self._content, 42


class _FakeContainer:
    def __init__(self, memory: _FakeMemoryService | None = None) -> None:
        self.memory_service = memory or _FakeMemoryService()

    def get_provider_spec(self, provider: str) -> dict | None:
        return {"api_endpoint": "https://example.test/v1"} if provider == "openrouter" else None

    def create_model_client(self, config) -> _FakeClient:  # noqa: ANN001
        return _FakeClient()


# ─── The flag is the contract ────────────────────────────────────────────────


def test_flag_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Off unless explicitly enabled — the HTTP response shape depends on it."""
    monkeypatch.delenv(synthesis.ENV_FLAG, raising=False)
    assert synthesis.http_llm_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_flag_truthy_values_enable(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(synthesis.ENV_FLAG, value)
    assert synthesis.http_llm_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "", "no", "off", "maybe"])
def test_flag_falsey_values_stay_off(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """A typo must leave the contract alone rather than half-enable it."""
    monkeypatch.setenv(synthesis.ENV_FLAG, value)
    assert synthesis.http_llm_enabled() is False


# ─── Synthesis behaviour ─────────────────────────────────────────────────────


@pytest.fixture
def _default_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the default-model lookup so tests do not read real user settings."""
    import app.adapters.web.settings as web_settings

    monkeypatch.setattr(
        web_settings, "get_default", lambda: {"provider": "openrouter", "model": "test/model"}
    )
    monkeypatch.setattr(web_settings, "resolve_api_key", lambda provider: "test-key")


@pytest.mark.asyncio
async def test_synthesize_returns_answer_shape(_default_model: None) -> None:
    container = _FakeContainer()
    result = await synthesis.synthesize_answer(container, "hello", "sess-1")

    assert result["response"] == "synthesized answer"
    assert result["model"] == {"provider": "openrouter", "id": "test/model"}
    assert result["tokens_used"] == 42


@pytest.mark.asyncio
async def test_memories_are_folded_in_as_data(_default_model: None) -> None:
    memory = _FakeMemoryService(memories=["user prefers tea", "user is in Freedonia"])
    container = _FakeContainer(memory)
    result = await synthesis.synthesize_answer(container, "what should I drink?", "sess-1")

    assert result["memories_used"] == 2


@pytest.mark.asyncio
async def test_memory_is_stored_user_turn_only(_default_model: None) -> None:
    """The assistant's reply is not stored — matches the web path's rationale."""
    memory = _FakeMemoryService()
    container = _FakeContainer(memory)
    await synthesis.synthesize_answer(container, "remember this", "sess-9")

    assert memory.stored == [("user_sess-9", "remember this")]


@pytest.mark.asyncio
async def test_recall_failure_does_not_block_synthesis(_default_model: None) -> None:
    """Recall is an enhancement; losing it must not cost the answer."""
    container = _FakeContainer(_FakeMemoryService(fail_recall=True))
    result = await synthesis.synthesize_answer(container, "hello", "sess-1")

    assert result["response"] == "synthesized answer"
    assert result["memories_used"] == 0


@pytest.mark.asyncio
async def test_model_failure_degrades_to_synthesis_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider outage must not turn a successful plan into a 5xx."""
    import app.adapters.web.settings as web_settings

    monkeypatch.setattr(
        web_settings, "get_default", lambda: {"provider": "openrouter", "model": "test/model"}
    )
    monkeypatch.setattr(web_settings, "resolve_api_key", lambda provider: "test-key")

    container = _FakeContainer()
    container.create_model_client = lambda config: _FakeClient(fail=True)  # type: ignore[method-assign]

    result = await synthesis.synthesize_answer(container, "hello", "sess-1")

    assert "synthesis_error" in result
    assert "response" not in result


@pytest.mark.asyncio
async def test_missing_default_model_reports_config_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.adapters.web.settings as web_settings

    monkeypatch.setattr(web_settings, "get_default", lambda: {"provider": "", "model": ""})

    result = await synthesis.synthesize_answer(_FakeContainer(), "hello", "sess-1")

    assert "synthesis_error" in result
    assert "model" in result["synthesis_error"].lower()


@pytest.mark.asyncio
async def test_agy_provider_reports_actionable_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """'agy' is CLI-backed and unreachable from the HTTP path.

    Without the explicit branch it fell through to get_provider_spec() and
    reported the misleading "Unknown provider 'agy'".
    """
    import app.adapters.web.settings as web_settings

    monkeypatch.setattr(
        web_settings, "get_default", lambda: {"provider": "agy", "model": "gemini-3.1-pro-high"}
    )

    result = await synthesis.synthesize_answer(_FakeContainer(), "hello", "sess-1")

    assert "synthesis_error" in result
    assert "CLI-backed" in result["synthesis_error"]
    assert "Unknown provider" not in result["synthesis_error"]


def test_extract_content_handles_client_shapes() -> None:
    """Clients disagree on their return type; the endpoint must not care."""
    assert synthesis._extract_content(("text", 7)) == ("text", 7)
    assert synthesis._extract_content("bare") == ("bare", None)

    class _Obj:
        content = "obj text"
        total_tokens = 3

    assert synthesis._extract_content(_Obj()) == ("obj text", 3)
