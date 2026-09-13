"""Unit tests for app/telemetry: logger, metrics, tracer."""

import asyncio
import logging
from unittest.mock import MagicMock

import pytest

from app.domain import StepStatus
from app.events import InMemoryAsyncBus, StepExecutionEvent, TelemetryEvent, TokenUsageEvent
from app.telemetry.logger import (
    OTEL_AGENT_NAME,
    OTEL_GUARDRAIL_RESULT,
    OTEL_TOOL_NAME,
    EventLogger,
)
from app.telemetry.metrics import MetricsCollector
from app.telemetry.tracer import Tracer


def test_otel_constants() -> None:
    assert OTEL_AGENT_NAME == "gen_ai.agent.name"
    assert OTEL_TOOL_NAME == "gen_ai.tool.name"
    assert OTEL_GUARDRAIL_RESULT == "gen_ai.guardrail.result"


def test_metrics_collector() -> None:
    collector = MetricsCollector()
    assert collector.metrics.total_requests == 0
    assert collector.metrics.total_tokens == 0
    assert collector.metrics.total_cost_usd == 0.0
    assert collector.metrics.failed_steps == 0

    collector.record_request(tokens=100, cost_usd=0.002)
    collector.record_request(tokens=50, cost_usd=0.001)
    collector.record_step_failure()

    assert collector.metrics.total_requests == 2
    assert collector.metrics.total_tokens == 150
    assert pytest.approx(collector.metrics.total_cost_usd) == 0.003
    assert collector.metrics.failed_steps == 1

    prom_text = collector.export_prometheus()
    assert "jarvis_requests_total 2" in prom_text
    assert "jarvis_tokens_total 150" in prom_text
    assert "jarvis_failed_steps_total 1" in prom_text


@pytest.mark.asyncio
async def test_event_logger_handlers(caplog: pytest.LogCaptureFixture) -> None:
    bus = InMemoryAsyncBus()
    event_logger = EventLogger(bus=bus)

    with caplog.at_level(logging.INFO, logger="jarvis.telemetry"):
        # Telemetry event
        te = TelemetryEvent(
            event_id="t1",
            event_type="telemetry",
            component="planner",
            category="latency",
            duration_ms=45.2,
            data={"model": "omni"},
        )
        await event_logger._on_telemetry(te)
        assert "[TELEMETRY]" in caplog.text
        assert "gen_ai.agent.name=planner" in caplog.text
        assert "duration=45.2ms" in caplog.text

        # Step execution event
        se = StepExecutionEvent(
            event_id="s1",
            event_type="step_execution",
            plan_id="p1",
            step_id="step_1",
            title="Read configuration",
            status=StepStatus.COMPLETED,
            error=None,
        )
        await event_logger._on_step_execution(se)
        assert "[STEP]" in caplog.text
        assert "plan=p1" in caplog.text
        assert "status=completed" in caplog.text

        # Token usage event
        tu = TokenUsageEvent(
            event_id="u1",
            event_type="token_usage",
            provider="openai",
            model="gpt-4o",
            total_tokens=1500,
            prompt_tokens=1000,
            completion_tokens=500,
            estimated_cost_usd=0.015,
        )
        await event_logger._on_token_usage(tu)
        assert "[COST AUDIT]" in caplog.text
        assert "provider=openai" in caplog.text
        assert "tokens=1500" in caplog.text


@pytest.mark.asyncio
async def test_tracer_with_and_without_bus() -> None:
    # 1. Tracer without bus
    tracer_no_bus = Tracer(bus=None)
    async with tracer_no_bus.trace("test_comp"):
        await asyncio.sleep(0.001)

    # 2. Tracer with bus
    mock_bus = MagicMock()
    tracer_bus = Tracer(bus=mock_bus)

    async with tracer_bus.trace("search_engine", category="query", metadata={"k": 5}):
        await asyncio.sleep(0.005)

    assert mock_bus.publish.call_count == 1
    published_event = mock_bus.publish.call_args[0][0]
    assert isinstance(published_event, TelemetryEvent)
    assert published_event.component == "search_engine"
    assert published_event.category == "query"
    assert published_event.duration_ms > 0
    assert published_event.data == {"k": 5}


@pytest.mark.asyncio
async def test_tracer_publishes_even_on_exception() -> None:
    mock_bus = MagicMock()
    tracer = Tracer(bus=mock_bus)

    with pytest.raises(ValueError):
        async with tracer.trace("faulty_component"):
            raise ValueError("Something went wrong")

    assert mock_bus.publish.call_count == 1
    published_event = mock_bus.publish.call_args[0][0]
    assert published_event.component == "faulty_component"
