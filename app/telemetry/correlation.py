"""Request correlation context (Migration Plan Step 2.5).

Re-export facade over ``app.events.correlation`` (the canonical home — see that
module for why the ``ContextVar`` cannot live here: the import-layering gate
holds ``app.events`` standalone, so the bus must read the ID without importing
``app.telemetry``). Both import paths share the single ``ContextVar`` object;
call sites outside the bus keep this telemetry-flavored path.
"""

from __future__ import annotations

from app.events.correlation import (
    correlation_id_ctx,
    get_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)

__all__ = [
    "correlation_id_ctx",
    "get_correlation_id",
    "reset_correlation_id",
    "set_correlation_id",
]
