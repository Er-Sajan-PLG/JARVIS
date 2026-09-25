"""Tests for contextvars correlation propagation (Migration Plan Step 2.5)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response

from app.events import Event, InMemoryAsyncBus
from app.telemetry.correlation import (
    get_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)


def _collector(received: list[Event]) -> Callable[[Event], Awaitable[None]]:
    async def _handle(event: Event) -> None:
        received.append(event)

    return _handle


async def test_bus_stamps_active_correlation_id() -> None:
    bus = InMemoryAsyncBus()
    received: list[Event] = []
    bus.subscribe("probe", _collector(received))

    token = set_correlation_id("req-abc")
    try:
        await bus.publish_async(Event(event_id="e1", event_type="probe"))
    finally:
        reset_correlation_id(token)

    assert received[0].metadata["correlation_id"] == "req-abc"


async def test_bus_falls_back_to_none_without_context() -> None:
    async def _child() -> Event:
        bus = InMemoryAsyncBus()
        received: list[Event] = []
        bus.subscribe("probe", _collector(received))
        await bus.publish_async(Event(event_id="e2", event_type="probe"))
        return received[0]

    assert get_correlation_id() == "none"  # no context leaked between tests
    event = await asyncio.create_task(_child())

    assert event.metadata.get("correlation_id", "none") == "none"


async def test_bus_preserves_explicit_correlation_id() -> None:
    bus = InMemoryAsyncBus()
    received: list[Event] = []
    bus.subscribe("probe", _collector(received))

    token = set_correlation_id("ctx-1")
    try:
        await bus.publish_async(
            Event(event_id="e3", event_type="probe", metadata={"correlation_id": "explicit"})
        )
    finally:
        reset_correlation_id(token)

    assert received[0].metadata["correlation_id"] == "explicit"


async def test_middleware_sets_and_resets_correlation_id() -> None:
    from app.main import logging_middleware

    seen: list[str] = []

    async def _call_next(request: Any) -> Any:
        seen.append(get_correlation_id())
        return Response("ok")

    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/health",
        "headers": [(b"x-correlation-id", b"cid-1")],
    }
    response = await logging_middleware(Request(scope), _call_next)

    assert seen == ["cid-1"]
    assert get_correlation_id() == "none"
    assert response.headers["X-Correlation-ID"] == "cid-1"
