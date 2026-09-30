"""Unit tests for app/models/router.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.exceptions import ModelRateLimitError
from app.models.interface import BaseLLMProvider, LLMResponse
from app.models.router import ModelRouter, TaskType


def make_mock_provider(name: str) -> BaseLLMProvider:
    provider = MagicMock(spec=BaseLLMProvider)
    provider.provider_name = name
    provider.is_available = AsyncMock(return_value=True)
    provider.generate_text = AsyncMock()
    return provider


def test_task_type_enum():
    assert TaskType.AUTOCOMPLETE == "autocomplete"
    assert TaskType.CODE == "code"
    assert TaskType.REASONING == "reasoning"
    assert TaskType.STEM == "stem"
    assert TaskType.GENERAL == "general"
    assert TaskType.DOCS == "docs"


def test_classify_prompt():
    router = ModelRouter()
    assert (
        router.classify_prompt("Write a python function to debug this syntax error")
        == TaskType.CODE
    )
    assert router.classify_prompt("Calculate the derivative and physics equation") == TaskType.STEM
    assert (
        router.classify_prompt("Analyze, reason and compare these two viewpoints")
        == TaskType.REASONING
    )
    assert router.classify_prompt("Generate the readme and tutorial walkthrough") == TaskType.DOCS
    assert router.classify_prompt("What is the weather today?") == TaskType.GENERAL


def test_register_provider_sets_default():
    router = ModelRouter()
    p1 = make_mock_provider("p1")
    p2 = make_mock_provider("p2")

    router.register_provider(p1)
    assert router.default_provider_name == "p1"

    router.register_provider(p2)
    assert router.default_provider_name == "p1"  # Keeps first by default

    router.register_provider(p2, default=True)
    assert router.default_provider_name == "p2"  # Explicit default overrides


def test_select_healthy_provider_preferred():
    rm = MagicMock()
    rm.health.is_available.return_value = True

    router = ModelRouter(resource_manager=rm)
    p1 = make_mock_provider("p1")
    p2 = make_mock_provider("p2")
    router.register_provider(p1)
    router.register_provider(p2)

    chosen = router.select_healthy_provider(preferred_provider="p2")
    assert chosen == p2


def test_select_healthy_provider_preferred_unhealthy_falls_back_to_default():
    rm = MagicMock()
    # p2 is unhealthy, p1 (default) is healthy
    rm.health.is_available.side_effect = lambda name: name == "p1"

    router = ModelRouter(resource_manager=rm)
    p1 = make_mock_provider("p1")
    p2 = make_mock_provider("p2")
    router.register_provider(p1)
    router.register_provider(p2)

    chosen = router.select_healthy_provider(preferred_provider="p2")
    assert chosen == p1


def test_select_healthy_provider_failover_pool():
    rm = MagicMock()
    # default (p1) is unhealthy, preferred not set, p2 is healthy
    rm.health.is_available.side_effect = lambda name: name == "p2"

    router = ModelRouter(resource_manager=rm)
    p1 = make_mock_provider("p1")
    p2 = make_mock_provider("p2")
    router.register_provider(p1)
    router.register_provider(p2)

    chosen = router.select_healthy_provider()
    assert chosen == p2


def test_select_healthy_provider_none_available_raises():
    rm = MagicMock()
    rm.health.is_available.return_value = False

    router = ModelRouter(resource_manager=rm)
    p1 = make_mock_provider("p1")
    router.register_provider(p1)

    with pytest.raises(RuntimeError, match="No healthy LLM providers available in failover pool"):
        router.select_healthy_provider()


@pytest.mark.asyncio
async def test_generate_success_primary():
    rm = MagicMock()
    rm.health.is_available.return_value = True

    router = ModelRouter(resource_manager=rm)
    p1 = make_mock_provider("p1")
    p1.generate_text.return_value = LLMResponse(
        content="answer",
        model="m1",
        provider="p1",
        total_tokens=20,
    )
    router.register_provider(p1)

    res = await router.generate("prompt", "m1")
    assert res.content == "answer"
    rm.health.record_success.assert_called_once_with("p1")
    rm.rate_limits.record_request.assert_called_once_with("p1", 20)


@pytest.mark.asyncio
async def test_generate_failover_on_429_rate_limit():
    rm = MagicMock()
    # Initially p1 and p2 both healthy
    health_status = {"p1": True, "p2": True}
    rm.health.is_available.side_effect = lambda name: health_status.get(name, False)

    def record_failure(name, code):
        health_status[name] = False

    rm.health.record_failure.side_effect = record_failure

    router = ModelRouter(resource_manager=rm)
    p1 = make_mock_provider("p1")
    p2 = make_mock_provider("p2")

    p1.generate_text.side_effect = Exception("429 Too Many Requests: Rate limit exceeded")
    p2.generate_text.return_value = LLMResponse(
        content="fallback answer", model="m1", provider="p2"
    )

    router.register_provider(p1)
    router.register_provider(p2)

    res = await router.generate("prompt", "m1", preferred_provider="p1")
    assert res.content == "fallback answer"
    rm.health.record_failure.assert_called_once_with("p1", 429)
    rm.health.record_success.assert_called_once_with("p2")


@pytest.mark.asyncio
async def test_generate_failover_on_the_real_rate_limit_exception():
    """The rate-limit path must work for the exception production actually raises.

    This test exists because the one above it passes for the wrong reason. It
    raises a hand-written `Exception("429 Too Many Requests: Rate limit
    exceeded")`, and `ModelRouter` classifies the failure by STRING-MATCHING the
    message (`router.py`: `"429" in err_str or "rate limit" in err_str.lower()`).
    The wording therefore satisfies the heuristic by construction.

    But no client raises that. All 11 provider clients map the provider's
    RateLimitError through `map_openai_error`, which builds the message
    `"Model '<name>' is rate-limited or over quota."` (exceptions.py). That
    string contains neither "429" nor "rate limit" -- the HYPHEN in
    "rate-limited" defeats the substring -- so the real exception was recorded
    with `code=None`, and the circuit breaker could not tell a rate limit from an
    unclassified failure. Verified by execution before this fix.

    A fake that satisfies a string heuristic proves the heuristic works on that
    fake's spelling, not that it works on production's.
    """
    rm = MagicMock()
    health_status = {"p1": True, "p2": True}
    rm.health.is_available.side_effect = lambda name: health_status.get(name, False)

    def record_failure(name, code):
        health_status[name] = False

    rm.health.record_failure.side_effect = record_failure

    router = ModelRouter(resource_manager=rm)
    p1 = make_mock_provider("p1")
    p2 = make_mock_provider("p2")

    # The exact message map_openai_error builds, via the real exception class.
    p1.generate_text.side_effect = ModelRateLimitError("Model 'm1' is rate-limited or over quota.")
    p2.generate_text.return_value = LLMResponse(
        content="fallback answer", model="m1", provider="p2"
    )

    router.register_provider(p1)
    router.register_provider(p2)

    res = await router.generate("prompt", "m1", preferred_provider="p1")
    assert res.content == "fallback answer"
    rm.health.record_failure.assert_called_once_with("p1", 429)


@pytest.mark.asyncio
async def test_generate_failover_on_503():
    rm = MagicMock()
    health_status = {"p1": True, "p2": True}
    rm.health.is_available.side_effect = lambda name: health_status.get(name, False)

    def record_failure(name, code):
        health_status[name] = False

    rm.health.record_failure.side_effect = record_failure

    router = ModelRouter(resource_manager=rm)
    p1 = make_mock_provider("p1")
    p2 = make_mock_provider("p2")

    p1.generate_text.side_effect = Exception("503 Service Unavailable")
    p2.generate_text.return_value = LLMResponse(content="recovered", model="m1", provider="p2")

    router.register_provider(p1)
    router.register_provider(p2)

    res = await router.generate("prompt", "m1")
    assert res.content == "recovered"
    rm.health.record_failure.assert_called_once_with("p1", 503)
    rm.health.record_success.assert_called_once_with("p2")
