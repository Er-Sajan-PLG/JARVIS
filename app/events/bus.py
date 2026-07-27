"""In-Memory Async Event Bus.

Reserved for passive telemetry, logging, metrics, background jobs, streaming events, and scheduler notifications.
Core execution loops MUST use direct async interface calls instead of the bus.
"""

import asyncio
import logging
from typing import Awaitable, Callable, TypeVar

from app.events.models import Event

logger = logging.getLogger(__name__)

E = TypeVar("E", bound=Event)
EventHandler = Callable[[E], Awaitable[None]]


class InMemoryAsyncBus:
    """Decoupled in-memory asynchronous event bus."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler[Any]]] = {}

    def subscribe(self, event_type: str, handler: EventHandler[Any]) -> None:
        """Register an async event handler for a specific event_type string."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug("Subscribed %s to event %s", handler.__name__, event_type)

    def unsubscribe(self, event_type: str, handler: EventHandler[Any]) -> None:
        """Remove a handler registration."""
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def publish_async(self, event: Event) -> None:
        """Publish an event and await all registered handlers concurrently."""
        handlers = self._handlers.get(event.event_type, []) + self._handlers.get("*", [])
        if not handlers:
            return

        tasks = [self._safe_execute(h, event) for h in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    def publish(self, event: Event) -> None:
        """Fire-and-forget event dispatch via background task."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish_async(event))
        except RuntimeError:
            # Fallback if no loop running (e.g. sync context or startup)
            logger.warning("No running asyncio event loop available for event %s", event.event_type)

    async def _safe_execute(self, handler: EventHandler[Any], event: Event) -> None:
        """Execute a single handler catching and logging exceptions so failure never propagates."""
        try:
            await handler(event)
        except Exception as err:
            logger.exception("Error executing event handler %s for event %s: %s", handler.__name__, event.event_id, err)
