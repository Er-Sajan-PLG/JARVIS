"""Unit tests for app/resources: budget, rate limits, provider health, manager."""

from unittest.mock import patch

import pytest

from app.resources.budget import TokenBudgetManager, TokenUsage
from app.resources.manager import ResourceManager
from app.resources.provider_health import CircuitState, ProviderHealthMonitor
from app.resources.rate_limits import RateLimitTracker


def test_token_usage_dataclass() -> None:
    usage = TokenUsage(
        prompt_tokens=10, completion_tokens=20, total_tokens=30, estimated_cost_usd=0.01
    )
    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 20
    assert usage.total_tokens == 30
    assert usage.estimated_cost_usd == 0.01


def test_token_budget_manager_record_and_get() -> None:
    mgr = TokenBudgetManager(max_session_tokens=1000)

    # Initial session usage should be empty
    usage = mgr.get_session_usage("sess_1")
    assert usage.total_tokens == 0
    assert usage.estimated_cost_usd == 0.0

    # Record first usage
    u1 = mgr.record_usage("sess_1", prompt_tokens=100, completion_tokens=50, cost_usd=0.002)
    assert u1.prompt_tokens == 100
    assert u1.completion_tokens == 50
    assert u1.total_tokens == 150
    assert u1.estimated_cost_usd == 0.002

    # Record second usage to same session
    u2 = mgr.record_usage("sess_1", prompt_tokens=200, completion_tokens=100, cost_usd=0.004)
    assert u2.prompt_tokens == 300
    assert u2.completion_tokens == 150
    assert u2.total_tokens == 450
    assert pytest.approx(u2.estimated_cost_usd) == 0.006

    # Distinct session
    u_other = mgr.get_session_usage("sess_2")
    assert u_other.total_tokens == 0


def test_token_budget_manager_is_within_budget() -> None:
    mgr = TokenBudgetManager(max_session_tokens=500)
    mgr.record_usage("s1", prompt_tokens=200, completion_tokens=200)  # total 400

    # 400 + 100 = 500 <= 500 -> True
    assert mgr.is_within_budget("s1", estimated_tokens=100) is True

    # 400 + 101 = 501 > 500 -> False
    assert mgr.is_within_budget("s1", estimated_tokens=101) is False

    # Default estimated_tokens is 1000 -> 400 + 1000 > 500 -> False
    assert mgr.is_within_budget("s1") is False


def test_rate_limit_tracker_rpm_and_tpm() -> None:
    tracker = RateLimitTracker(window_seconds=60)
    current_time = 1000.0

    with patch("time.time", return_value=current_time):
        tracker.record_request("openai", token_count=150)
        tracker.record_request("openai", token_count=250)
        tracker.record_request("anthropic", token_count=100)

        assert tracker.get_rpm("openai") == 2
        assert tracker.get_tpm("openai") == 400
        assert tracker.get_rpm("anthropic") == 1
        assert tracker.get_tpm("anthropic") == 100
        assert tracker.get_rpm("unknown") == 0
        assert tracker.get_tpm("unknown") == 0

    # Advance time past the 60s window
    with patch("time.time", return_value=current_time + 65.0):
        # Requests from t=1000.0 should be pruned
        assert tracker.get_rpm("openai") == 0
        assert tracker.get_tpm("openai") == 0

        # New request in the new window
        tracker.record_request("openai", token_count=50)
        assert tracker.get_rpm("openai") == 1
        assert tracker.get_tpm("openai") == 50


def test_provider_health_circuit_states() -> None:
    monitor = ProviderHealthMonitor(failure_threshold=3, recovery_time_seconds=30.0)

    assert monitor.is_available("groq") is True

    # 2 failures: still CLOSED and available
    monitor.record_failure("groq")
    monitor.record_failure("groq")
    assert monitor.is_available("groq") is True

    # 3rd failure: threshold reached -> OPEN
    monitor.record_failure("groq")
    assert monitor.is_available("groq") is False

    # Immediate check before recovery time
    current_time = 1000.0
    with patch("time.time", return_value=current_time):
        monitor.record_failure("groq")
        assert monitor.is_available("groq") is False

    # Check after recovery time expires -> should transition to HALF_OPEN and return True
    with patch("time.time", return_value=current_time + 31.0):
        assert monitor.is_available("groq") is True
        assert monitor._states["groq"] == CircuitState.HALF_OPEN

        # While HALF_OPEN, is_available returns True
        assert monitor.is_available("groq") is True

        # Successful probe resets to CLOSED
        monitor.record_success("groq")
        assert monitor._states["groq"] == CircuitState.CLOSED
        assert monitor._consecutive_failures["groq"] == 0
        assert monitor.is_available("groq") is True


def test_provider_health_status_codes_open_immediately() -> None:
    monitor = ProviderHealthMonitor(failure_threshold=5)

    # 429 rate limit error opens circuit immediately
    monitor.record_failure("cerebras", error_code=429)
    assert monitor._states["cerebras"] == CircuitState.OPEN
    assert monitor.is_available("cerebras") is False

    # Reset
    monitor.record_success("cerebras")
    assert monitor.is_available("cerebras") is True

    # 503 service unavailable error opens circuit immediately
    monitor.record_failure("cerebras", error_code=503)
    assert monitor._states["cerebras"] == CircuitState.OPEN
    assert monitor.is_available("cerebras") is False


def test_resource_manager_facade() -> None:
    rm = ResourceManager()
    assert isinstance(rm.budget, TokenBudgetManager)
    assert isinstance(rm.rate_limits, RateLimitTracker)
    assert isinstance(rm.health, ProviderHealthMonitor)
