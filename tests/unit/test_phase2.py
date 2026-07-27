"""Unit tests for Phase 2: BaseLLMProvider, ModelRouter, ResourceManager, ProviderHealthMonitor.
"""

from typing import AsyncGenerator
import pytest

from app.models.interface import BaseLLMProvider, LLMResponse
from app.models.router import ModelRouter, TaskType
from app.resources import CircuitState, ProviderHealthMonitor, ResourceManager, TokenBudgetManager


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM Provider for unit testing."""

    def __init__(self, name: str = "mock", available: bool = True, fail_code: int | None = None) -> None:
        self._name = name
        self._available = available
        self._fail_code = fail_code

    @property
    def provider_name(self) -> str:
        return self._name

    async def is_available(self, api_key: str | None = None) -> bool:
        return self._available

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
        if self._fail_code:
            raise RuntimeError(f"API Error {self._fail_code}")
        return LLMResponse(
            content=f"Response from {self._name}: {prompt}",
            model=model,
            provider=self._name,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )

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
        yield f"Token from {self._name}"


def test_token_budget_manager() -> None:
    """Verify TokenBudgetManager tracks tokens and limits."""
    tbm = TokenBudgetManager(max_session_tokens=100)
    assert tbm.is_within_budget("sess_1", estimated_tokens=50) is True

    tbm.record_usage("sess_1", prompt_tokens=40, completion_tokens=50, cost_usd=0.01)
    usage = tbm.get_session_usage("sess_1")
    assert usage.total_tokens == 90
    assert usage.estimated_cost_usd == 0.01

    assert tbm.is_within_budget("sess_1", estimated_tokens=20) is False


def test_provider_health_circuit_breaker() -> None:
    """Verify ProviderHealthMonitor opens circuit on failures."""
    ph = ProviderHealthMonitor(failure_threshold=2, recovery_time_seconds=10.0)
    assert ph.is_available("groq") is True

    ph.record_failure("groq", error_code=429)
    assert ph.is_available("groq") is False
    assert ph._states["groq"] == CircuitState.OPEN

    ph.record_success("groq")
    assert ph.is_available("groq") is True


def test_model_router_classification_and_failover() -> None:
    """Verify ModelRouter classifies prompts and fails over to healthy providers."""
    import asyncio

    async def _run() -> None:
        rm = ResourceManager()
        router = ModelRouter(resource_manager=rm)

        p1 = MockLLMProvider("failing_provider", fail_code=429)
        p2 = MockLLMProvider("healthy_provider")

        router.register_provider(p1, default=True)
        router.register_provider(p2)

        # Task classification test
        task = router.classify_prompt("Write a python function to refactor code")
        assert task == TaskType.CODE

        # Execute generate, expecting failover to healthy_provider
        res = await router.generate("Hello", model="test-model", preferred_provider="failing_provider")
        assert res.provider == "healthy_provider"
        assert "Response from healthy_provider" in res.content

    asyncio.run(_run())
