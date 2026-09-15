"""Temporal status must reach the model, not just the disk (ADR-015).

Storing valid_at/invalid_at is worthless if the prompt renders an ended job and
a current job identically. These tests pin the rendered suffix, because that
string is what actually determines whether JARVIS says "I work at RUCHI" or
"I left RUCHI".

They use the real ``MemoryRecord`` domain type rather than a stand-in, so a
field renamed on the domain object breaks these tests instead of silently
rendering nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.context.builder import _temporal_suffix
from app.domain import MemoryRecord


def _rec(**kw: object) -> MemoryRecord:
    base: dict[str, object] = {"id": "abc12345", "key": "role", "value": "Civil Engineer"}
    base.update(kw)
    return MemoryRecord(**base)  # type: ignore[arg-type]


def _ts(y: int, m: int, d: int, hh: int = 0) -> float:
    return datetime(y, m, d, hh, tzinfo=UTC).timestamp()


def test_ended_fact_is_marked_ended() -> None:
    """The RUCHI/Roadshow case: a finished job must not read as current."""
    rec = _rec(valid_at=_ts(2025, 8, 1), invalid_at=_ts(2025, 11, 30))
    assert _temporal_suffix(rec) == " [ended 2025-11-30]"


def test_live_fact_shows_since() -> None:
    rec = _rec(valid_at=_ts(2023, 6, 1))
    assert _temporal_suffix(rec) == " [since 2023-06-01]"


def test_upcoming_event_is_marked_upcoming() -> None:
    future = datetime.now(UTC).timestamp() + 86400 * 30
    assert "[upcoming:" in _temporal_suffix(_rec(occurs_at=future))


def test_past_event_is_marked_past() -> None:
    past = datetime.now(UTC).timestamp() - 86400 * 30
    assert "[past event:" in _temporal_suffix(_rec(occurs_at=past))


def test_ended_takes_priority_over_occurs() -> None:
    """A fact that both has an event time and has ended shows the ending."""
    rec = _rec(valid_at=_ts(2025, 8, 1), invalid_at=_ts(2025, 11, 30), occurs_at=_ts(2025, 8, 1))
    assert _temporal_suffix(rec).startswith(" [ended")


def test_untimed_record_renders_nothing() -> None:
    """Pre-migration records must render exactly as they did before."""
    assert _temporal_suffix(_rec()) == ""


def test_missing_attributes_do_not_raise() -> None:
    """A lightweight object without the fields must not break prompt assembly."""

    class Bare:
        pass

    assert _temporal_suffix(Bare()) == ""  # type: ignore[arg-type]


def test_suffix_is_usable_in_a_prompt_line() -> None:
    rec = _rec(valid_at=_ts(2025, 8, 1), invalid_at=_ts(2025, 11, 30))
    line = f"- [profession] role: Civil Engineer{_temporal_suffix(rec)}"
    assert line.endswith("[ended 2025-11-30]")
