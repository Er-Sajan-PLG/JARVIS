"""Unit tests for app/models/interface.py."""

from collections.abc import AsyncGenerator

import pytest

from app.models.interface import BaseLLMProvider, LLMResponse


def test_llm_response_defaults():
    resp = LLMResponse(content="hello", model="test-model", provider="test-provider")
    assert resp.content == "hello"
    assert resp.model == "test-model"
    assert resp.provider == "test-provider"
    assert resp.prompt_tokens == 0
    assert resp.completion_tokens == 0
    assert resp.total_tokens == 0
    assert resp.metadata == {}


def test_llm_response_custom_values():
    resp = LLMResponse(
        content="world",
        model="m1",
        provider="p1",
        prompt_tokens=10,
        completion_tokens=25,
        total_tokens=35,
        metadata={"finish_reason": "stop"},
    )
    assert resp.prompt_tokens == 10
    assert resp.completion_tokens == 25
    assert resp.total_tokens == 35
    assert resp.metadata == {"finish_reason": "stop"}


def test_base_llm_provider_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseLLMProvider()


@pytest.mark.asyncio
async def test_concrete_llm_provider_implementation():
    class DummyProvider(BaseLLMProvider):
        @property
        def provider_name(self) -> str:
            return "dummy"

        async def is_available(self, api_key: str | None = None) -> bool:
            return True

        async def generate_text(
            self,
            prompt: str,
            model: str,
            system_prompt: str | None = None,
            temperature: float = 0.7,
            max_tokens: int = 4096,
            api_key: str | None = None,
            extra_headers: dict[str, str] | None = None,
        ) -> LLMResponse:
            return LLMResponse(content=f"echo:{prompt}", model=model, provider=self.provider_name)

        async def stream_text(
            self,
            prompt: str,
            model: str,
            system_prompt: str | None = None,
            temperature: float = 0.7,
            max_tokens: int = 4096,
            api_key: str | None = None,
            extra_headers: dict[str, str] | None = None,
        ) -> AsyncGenerator[str, None]:
            for tok in prompt.split():
                yield tok

    provider = DummyProvider()
    assert provider.provider_name == "dummy"
    assert await provider.is_available() is True

    res = await provider.generate_text("test prompt", "dummy-model")
    assert res.content == "echo:test prompt"
    assert res.model == "dummy-model"

    tokens = [tok async for tok in provider.stream_text("foo bar", "dummy-model")]
    assert tokens == ["foo", "bar"]
