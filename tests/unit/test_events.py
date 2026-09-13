"""Unit tests for app/events models and InMemoryAsyncBus."""

import asyncio
from datetime import datetime

import pytest

from app.domain import SafetyTier, StepStatus
from app.events.bus import InMemoryAsyncBus
from app.events.models import (
    Event,
    HITLRequestEvent,
    NotificationEvent,
    StepExecutionEvent,
    TelemetryEvent,
    TokenUsageEvent,
)


def test_event_models_instantiation() -> None:
    # Base Event
    ev = Event(event_id="e1", event_type="test")
    assert ev.event_id == "e1"
    assert ev.event_type == "test"
    assert isinstance(ev.timestamp, datetime)
    assert ev.metadata == {}

    # TelemetryEvent
    te = TelemetryEvent(
        event_id="t1",
        event_type="telemetry",
        duration_ms=12.5,
        data={"latency": 12},
    )
    assert te.category == "telemetry"
    assert te.component == "system"
    assert te.duration_ms == 12.5
    assert te.data == {"latency": 12}

    # StepExecutionEvent
    se = StepExecutionEvent(
        event_id="s1",
        event_type="step_execution",
        plan_id="p1",
        step_id="step_1",
        title="Execute command",
        status=StepStatus.COMPLETED,
        result="success",
        error=None,
    )
    assert se.plan_id == "p1"
    assert se.status == StepStatus.COMPLETED
    assert se.result == "success"

    # HITLRequestEvent
    he = HITLRequestEvent(
        event_id="h1",
        event_type="hitl_request",
        plan_id="p1",
        step_id="step_2",
        tool_name="bash",
        arguments={"cmd": "rm -rf"},
        safety_tier=SafetyTier.DESTRUCTIVE,
        description="Delete dir",
    )
    assert he.tool_name == "bash"
    assert he.safety_tier == SafetyTier.DESTRUCTIVE

    # TokenUsageEvent
    tue = TokenUsageEvent(
        event_id="tu1",
        event_type="token_usage",
        provider="anthropic",
        model="claude-3-5",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        estimated_cost_usd=0.005,
    )
    assert tue.provider == "anthropic"
    assert tue.total_tokens == 150
    assert tue.estimated_cost_usd == 0.005

    # NotificationEvent
    ne = NotificationEvent(
        event_id="n1",
        event_type="notification",
        title="Job complete",
        message="Build finished successfully",
        level="info",
    )
    assert ne.title == "Job complete"
    assert ne.level == "info"


@pytest.mark.asyncio
async def test_bus_subscribe_and_publish_async() -> None:
    bus = InMemoryAsyncBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe("test_event", handler)
    # Duplicate subscription should be ignored
    bus.subscribe("test_event", handler)

    ev = Event(event_id="e1", event_type="test_event")
    await bus.publish_async(ev)

    assert len(received) == 1
    assert received[0].event_id == "e1"


@pytest.mark.asyncio
async def test_bus_wildcard_subscription() -> None:
    bus = InMemoryAsyncBus()
    received_wildcard: list[Event] = []
    received_specific: list[Event] = []

    async def wildcard_handler(event: Event) -> None:
        received_wildcard.append(event)

    async def specific_handler(event: Event) -> None:
        received_specific.append(event)

    bus.subscribe("*", wildcard_handler)
    bus.subscribe("custom_event", specific_handler)

    ev1 = Event(event_id="e1", event_type="custom_event")
    await bus.publish_async(ev1)

    assert len(received_specific) == 1
    assert len(received_wildcard) == 1

    ev2 = Event(event_id="e2", event_type="other_event")
    await bus.publish_async(ev2)

    assert len(received_specific) == 1
    assert len(received_wildcard) == 2


@pytest.mark.asyncio
async def test_bus_unsubscribe() -> None:
    bus = InMemoryAsyncBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe("test_event", handler)
    bus.unsubscribe("test_event", handler)
    # Unsubscribe non-registered handler or event type
    bus.unsubscribe("test_event", handler)
    bus.unsubscribe("non_existent", handler)

    ev = Event(event_id="e1", event_type="test_event")
    await bus.publish_async(ev)

    assert len(received) == 0


@pytest.mark.asyncio
async def test_bus_handler_exception_does_not_propagate() -> None:
    bus = InMemoryAsyncBus()
    successful: list[str] = []

    async def failing_handler(event: Event) -> None:
        raise RuntimeError("Handler failed!")

    async def succeeding_handler(event: Event) -> None:
        successful.append(event.event_id)

    bus.subscribe("test_event", failing_handler)
    bus.subscribe("test_event", succeeding_handler)

    ev = Event(event_id="e1", event_type="test_event")
    # Should not raise exception
    await bus.publish_async(ev)

    assert successful == ["e1"]


@pytest.mark.asyncio
async def test_bus_publish_fire_and_forget() -> None:
    bus = InMemoryAsyncBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe("async_fire", handler)

    ev = Event(event_id="f1", event_type="async_fire")
    bus.publish(ev)

    # Allow task in running loop to run
    await asyncio.sleep(0.01)
    assert len(received) == 1
    assert received[0].event_id == "f1"


def test_bus_publish_no_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    bus = InMemoryAsyncBus()
    monkeypatch.setattr(
        asyncio, "get_running_loop", lambda: (_ for _ in ()).throw(RuntimeError("No loop"))
    )

    ev = Event(event_id="noloop", event_type="noloop_event")
    # Should not raise
    bus.publish(ev)


@pytest.mark.asyncio
async def test_bus_publish_no_handlers() -> None:
    bus = InMemoryAsyncBus()
    ev = Event(event_id="empty", event_type="unhandled")
    # Should do nothing and not raise
    await bus.publish_async(ev)
