"""Request correlation context (canonical home).

Holds the ``X-Correlation-ID`` ``ContextVar`` born in
``app/main.py:logging_middleware``. It lives in ``app.events`` (rather than
``app.telemetry``) because the import-layering gate
(``scripts/board/review.py``) holds ``app.events`` standalone: the bus must be
able to read the active ID without importing any other ``app.*`` package.

``app/telemetry/correlation.py`` re-exports this module's names so call sites
outside the bus keep the telemetry-flavored import path; both paths share the
single ``ContextVar`` object defined here.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="none")


def set_correlation_id(correlation_id: str) -> Token[str]:
    """Bind a correlation ID in the current context. Returns a reset token."""
    return correlation_id_ctx.set(correlation_id)


def get_correlation_id() -> str:
    """Return the active correlation ID, or ``"none"`` outside a request."""
    return correlation_id_ctx.get()


def reset_correlation_id(token: Token[str]) -> None:
    """Restore the context to its state before the matching set call."""
    correlation_id_ctx.reset(token)
