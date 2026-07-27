"""Unit tests for Phase 5: Telemetry, EventLogger, Tracer, MetricsCollector, and bootstrap Composition Root.
"""

import pytest

from app.bootstrap import ApplicationContainer, bootstrap_system
from app.events import InMemoryAsyncBus, TelemetryEvent, TokenUsageEvent
from app.telemetry import EventLogger, MetricsCollector, Tracer


def test_telemetry_and_event_logger() -> None:
    """Verify EventLogger and Tracer process events over InMemoryAsyncBus."""
    import asyncio

    async def _run() -> None:
        bus = InMemoryAsyncBus()
        logger_sub = EventLogger(bus=bus)
        tracer = Tracer(bus=bus)

        telemetry_events = []
        bus.subscribe("telemetry", lambda e: telemetry_events.append(e))

        async with tracer.trace("brain", category="test_op"):
            await asyncio.sleep(0.01)

        await asyncio.sleep(0.05)  # allow task dispatch
        assert len(telemetry_events) == 1
        assert telemetry_events[0].component == "brain"
        assert telemetry_events[0].duration_ms > 0.0

    asyncio.run(_run())


def test_metrics_collector() -> None:
    """Verify MetricsCollector aggregates request token and cost totals."""
    mc = MetricsCollector()
    mc.record_request(tokens=100, cost_usd=0.005)
    mc.record_request(tokens=200, cost_usd=0.010)
    mc.record_step_failure()

    assert mc.metrics.total_requests == 2
    assert mc.metrics.total_tokens == 300
    assert abs(mc.metrics.total_cost_usd - 0.015) < 1e-6
    assert mc.metrics.failed_steps == 1


def test_bootstrap_composition_root() -> None:
    """Verify bootstrap_system returns fully wired ApplicationContainer."""
    container = bootstrap_system()
    assert isinstance(container, ApplicationContainer)
    assert container.event_bus is not None
    assert container.session_manager is not None
    assert container.model_router is not None
    assert container.task_planner is not None
    assert container.execution_runner is not None
