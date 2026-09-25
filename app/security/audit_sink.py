"""Append-only JSONL audit sink (Migration Plan Step 1).

Subscribes to the existing ``InMemoryAsyncBus`` (``app/events/bus.py``) and writes
one redacted JSONL line per event to ``data/audit/YYYY-MM-DD.jsonl``.

Design notes (verified against source before writing):
- Bus API is ``subscribe(event_type: str, handler)`` (``app/events/bus.py:28``).
  We subscribe ONLY to the ``"*"`` wildcard (``bus.py:43`` dispatches every event
  to wildcard handlers). Subscribing to both a concrete type and ``"*"`` would
  invoke this handler twice per event and double-write lines.
- Observed event types: ``"token_usage"`` (``app/telemetry/logger.py:31``),
  ``"step_execution"`` (``logger.py:30``, ``app/brain/runner.py:139-149``),
  ``"hitl_request"`` (``app/brain/runner.py:116-127``), ``"telemetry"``
  (``logger.py:29``, ``app/telemetry/tracer.py:105``).
- ``app/guardrails/approvals.py`` currently publishes NOTHING to the bus; the
  wildcard subscription covers future approval events without code changes here.
- Fire-and-forget: ``on_event`` never raises. Any failure (including the file
  write itself) is logged via structlog and swallowed so the hot path and the
  bus ``_safe_execute`` wrapper (``bus.py:59-69``) never see it propagate.

RULES FOR THIS MODULE: no request-path changes, no prompt changes, no config
changes. New code only.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import structlog

from app.events import Event, InMemoryAsyncBus

log = structlog.get_logger()

REDACTED = "[REDACTED]"
CONTENT_TRUNCATE_AT = 500

# Keys whose values are secrets and must never land in the audit file.
# Match rule (case-insensitive, '-' normalized to '_'): exact match OR
# "_"-suffixed match, so "api_key" catches "openrouter_api_key" and "token"
# catches "bot_token" — but "total_tokens"/"prompt_tokens" (counts, not secrets)
# are preserved because they do not end at a "_" boundary.
_REDACT_KEYS = frozenset(
    {
        "api_key",
        "token",
        "secret",
        "password",
        "authorization",
        "cookie",
        "email_body",
        "voice_bytes",
    }
)


def _match_rule(key: str) -> str:
    """Return 'redact', 'truncate', or 'keep' for a payload key."""
    norm = key.lower().replace("-", "_")
    if norm == "content":
        return "truncate"
    for blocked in _REDACT_KEYS:
        if norm == blocked or norm.endswith("_" + blocked):
            return "redact"
    return "keep"


def _redact_value(key: str, value: Any) -> Any:
    """Redact/truncate a single key/value pair, recursing into containers."""
    rule = _match_rule(key)
    if rule == "redact":
        return REDACTED
    if rule == "truncate" and isinstance(value, str) and len(value) > CONTENT_TRUNCATE_AT:
        return value[:CONTENT_TRUNCATE_AT] + "...[truncated]"
    if isinstance(value, dict):
        return {k: _redact_value(str(k), v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_redact_value(key, item) for item in value]
    return value


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a redacted copy of an event payload dict."""
    return {k: _redact_value(str(k), v) for k, v in payload.items()}


def _event_details(event: Event) -> dict[str, Any]:
    """Extract the auditable payload: dataclass fields minus envelope, redacted."""
    if is_dataclass(event) and not isinstance(event, type):
        payload = {
            k: v for k, v in asdict(cast(Any, event)).items() if k not in ("event_id", "event_type")
        }
        # asdict() keeps the timestamp datetime; the envelope carries the timestamp,
        # so drop it from details to avoid duplication (and non-JSON types).
        payload.pop("timestamp", None)
    else:  # pragma: no cover - Event is a dataclass today; defensive branch.
        payload = dict(event.metadata)
    return redact_payload(payload)


def _actor_action(event: Event) -> tuple[str, str]:
    """Derive (actor, action) from the event type. Unknown types -> system/passthrough."""
    event_type = event.event_type
    if event_type == "token_usage":
        return "llm", "token_usage"
    if event_type == "hitl_request":
        return "system", "hitl_request"
    if event_type == "step_execution":
        status = getattr(event, "status", None)
        status_value = getattr(status, "value", status)
        return "tool", f"step_{status_value}"
    return "system", event_type


class AuditSink:
    """Durable JSONL audit writer subscribed to the passive event bus."""

    def __init__(self, sink_dir: str | Path = "data/audit") -> None:
        self.sink_dir = Path(sink_dir)

    def attach(self, bus: InMemoryAsyncBus) -> InMemoryAsyncBus:
        """Subscribe to every present and future bus event via the wildcard."""
        bus.subscribe("*", self.on_event)
        return bus

    def _record(self, event: Event) -> dict[str, Any]:
        timestamp = event.timestamp
        if not isinstance(timestamp, datetime):
            timestamp = datetime.now(UTC)
        actor, action = _actor_action(event)
        return {
            "timestamp": timestamp.isoformat(),
            "correlation_id": event.metadata.get("correlation_id", "none"),
            "event_type": event.event_type,
            "actor": actor,
            "action": action,
            "details": _event_details(event),
        }

    def _write_line(self, record: dict[str, Any], day: str) -> None:
        self.sink_dir.mkdir(parents=True, exist_ok=True)
        path = self.sink_dir / f"{day}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")

    async def on_event(self, event: Event) -> None:
        """Bus handler. NEVER raises — failures are logged and swallowed."""
        try:
            record = self._record(event)
            day = record["timestamp"][:10]  # YYYY-MM-DD prefix of ISO 8601
            self._write_line(record, day)
        except Exception as err:  # noqa: BLE001 - sink must never break the bus
            log.warning("audit_sink.write_failed", error=str(err))


def audit_sink_enabled() -> bool:
    """Kill-switch for the sink. ``JARVIS_AUDIT_SINK=0`` disables it."""
    return os.getenv("JARVIS_AUDIT_SINK", "1") == "1"


def maybe_attach_sink(bus: InMemoryAsyncBus) -> AuditSink | None:
    """Create and attach the sink unless disabled. Returns None when disabled."""
    if not audit_sink_enabled():
        return None
    sink = AuditSink()
    sink.attach(bus)
    return sink
