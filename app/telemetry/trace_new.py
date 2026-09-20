"""Tracing helpers for the newer surfaces (Sprint 11.2).

The cognitive brain already traces its nodes. The comms, mesh and sub-agent
surfaces were added after that and had no spans, so the OTLP trace was honest
about the brain but silent on the parts an operator actually waits on (email,
notify, worker spawn). These helpers close that gap.

Layering: ``app.telemetry`` may only import ``app.events``, so this module
never imports the container. Instead the composition root registers the
``Tracer`` here once at boot; every helper degrades to a no-op until then.
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")

_tracer = None


def register_tracer(tracer) -> None:
    """Set the app tracer once at boot (called by the composition root)."""
    global _tracer
    _tracer = tracer


@contextlib.asynccontextmanager
async def traced(component: str, category: str = "operation"):
    """Async span over ``component`` using the registered tracer.

    No-op when no tracer is registered (unit tests, standalone runs) —
    telemetry must never be the thing that breaks a call.
    """
    if _tracer is None:
        yield
        return
    async with _tracer.trace(component=component, category=category):
        yield


async def traced_call(
    component: str, fn: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
) -> T:
    """Run ``fn(*args, **kwargs)`` under a ``component`` span."""
    async with traced(component):
        return await fn(*args, **kwargs)
