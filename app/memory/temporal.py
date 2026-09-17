"""Bi-temporal memory: two clocks, invalidation instead of deletion.

Design is ADR-015 (``docs/adr/ADR-015-memory-is-bi-temporal.md``). The model is
borrowed from Zep/Graphiti's temporal knowledge graph, reduced to the parts that
earn their keep in a single-user, single-machine store:

- **Event time** (``valid_at`` / ``invalid_at``) — when a fact was true in the
  world. ``valid_at`` may be in the past (a job that ended last year) and
  ``invalid_at`` may be set because the world changed, not because we learned
  anything new.
- **System time** (``created_at`` / ``expired_at``) — when this store learned
  the fact and when it stopped believing it. This is the audit clock.

Keeping the two apart is what lets one store answer both "what is true now" and
"what did we believe on 2026-09-14". A single clock cannot: the day we correct a
fact is usually not the day the fact stopped being true.

Two rules carry most of the value and are enforced here:

1. **Invalidate, never delete.** A superseding fact closes the old fact's
   interval and links forward. The old fact stays readable. This is the property
   whose absence destroyed real data on 2026-09-15.
2. **The model judges meaning; code does the arithmetic.** Deciding whether two
   facts contradict is a language call. Deciding which came first and which
   timestamps to set is arithmetic and is done here, deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

__all__ = [
    "TemporalFact",
    "Resolution",
    "close_interval",
    "is_valid_at",
    "select_current",
    "select_as_of",
    "find_superseded_by",
    "parse_occurs_at",
    "has_occurred",
    "upcoming",
    "format_occurs_at",
]


def _ts(value: Any) -> float | None:
    """Coerce a stored timestamp to epoch seconds, or None."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=UTC)
        return dt.timestamp()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


@dataclass
class TemporalFact:
    """A fact with two independent validity clocks.

    ``valid_at``/``invalid_at`` are event time; ``created_at``/``expired_at``
    are system time. ``None`` on an end field means "still open" — it is not the
    same as "unknown", which is why an unset ``valid_at`` is treated as open
    rather than as an error.
    """

    record_id: str
    valid_at: float | None = None
    invalid_at: float | None = None
    created_at: float | None = None
    expired_at: float | None = None
    superseded_by: str | None = None
    supersedes: str | None = None
    source: str = ""

    def is_current(self, at: float | None = None) -> bool:
        """True when the store believes this fact at ``at`` (default: now).

        Requires **both** clocks open: the world still holds it (event time) and
        we still believe it (system time).
        """
        now = at if at is not None else datetime.now(UTC).timestamp()
        if self.expired_at is not None and self.expired_at <= now:
            return False
        if self.invalid_at is not None and self.invalid_at <= now:
            return False
        # A fact whose validity has not started yet is not yet current.
        return not (self.valid_at is not None and self.valid_at > now)

    def was_believed_at(self, at: float) -> bool:
        """True when the store believed this fact at system time ``at``.

        Ignores event time — this is the audit-trail question ("what did we
        think then?"), not the world question.
        """
        if self.created_at is not None and self.created_at > at:
            return False
        return not (self.expired_at is not None and self.expired_at <= at)

    def overlaps(self, other: TemporalFact) -> bool:
        """Whether two facts' event-time intervals overlap.

        An open end is treated as extending to infinity. Used to avoid
        invalidating facts that simply describe a different period — "Bob ran
        5 miles on Tuesday" must not invalidate "Bob ran 3 miles on Wednesday".
        """
        a_start = self.valid_at if self.valid_at is not None else float("-inf")
        a_end = self.invalid_at if self.invalid_at is not None else float("inf")
        b_start = other.valid_at if other.valid_at is not None else float("-inf")
        b_end = other.invalid_at if other.invalid_at is not None else float("inf")
        return a_start < b_end and b_start < a_end

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TemporalFact:
        return cls(
            record_id=str(d.get("id") or d.get("record_id") or ""),
            valid_at=_ts(d.get("valid_at")),
            invalid_at=_ts(d.get("invalid_at")),
            created_at=_ts(d.get("created_at")),
            expired_at=_ts(d.get("expired_at")),
            superseded_by=d.get("superseded_by"),
            supersedes=d.get("supersedes"),
            source=str(d.get("source") or ""),
        )


@dataclass
class Resolution:
    """The outcome of retiring ``old`` in favour of ``new``."""

    old_id: str
    new_id: str
    invalid_at: float
    expired_at: float
    reason: str = ""
    applied: bool = True
    notes: list[str] = field(default_factory=list)


def close_interval(
    old: TemporalFact,
    new: TemporalFact,
    now: float | None = None,
    reason: str = "",
) -> Resolution:
    """Retire ``old`` because ``new`` supersedes it, without deleting either.

    Deterministic interval arithmetic: the model decides *whether* the two
    conflict (that is a language judgement and is done upstream), and this
    function decides *which timestamps* result. No LLM is involved here, so an
    ordering cannot be hallucinated.

    The old fact's ``invalid_at`` is pinned to the new fact's ``valid_at`` when
    the new fact has one and it is later than the old fact's start — the moment
    the world changed. Its ``expired_at`` is when we learned about it, which is
    now. When the new fact has no usable ``valid_at``, the old fact is closed at
    ``now`` on both clocks.

    Refuses to close a fact whose event interval does not overlap the new one:
    disjoint periods are different facts, not a correction.
    """
    stamp = now if now is not None else datetime.now(UTC).timestamp()

    if not old.overlaps(new) and new.valid_at is not None:
        return Resolution(
            old_id=old.record_id,
            new_id=new.record_id,
            invalid_at=0.0,
            expired_at=0.0,
            reason="non-overlapping event times — different periods, not a correction",
            applied=False,
            notes=[
                f"old valid_at={old.valid_at} invalid_at={old.invalid_at}",
                f"new valid_at={new.valid_at}",
            ],
        )

    # World time: the old fact stopped being true when the new one began.
    invalid_at = new.valid_at if new.valid_at is not None else stamp
    if old.valid_at is not None and invalid_at < old.valid_at:
        # New fact predates the old one (out-of-order ingestion). The old fact
        # was never true after the new one began, but we only learned this now.
        invalid_at = old.valid_at
        notes = ["new fact predates old — interval clamped to old valid_at"]
    else:
        notes = []

    return Resolution(
        old_id=old.record_id,
        new_id=new.record_id,
        invalid_at=invalid_at,
        expired_at=stamp,
        reason=reason or "superseded",
        applied=True,
        notes=notes,
    )


def is_valid_at(fact: TemporalFact, at: float) -> bool:
    """Whether the fact's event-time interval contains ``at``."""
    if fact.valid_at is not None and fact.valid_at > at:
        return False
    return not (fact.invalid_at is not None and fact.invalid_at <= at)


def select_current(facts: list[TemporalFact], at: float | None = None) -> list[TemporalFact]:
    """Facts the store currently believes. The default read path."""
    return [f for f in facts if f.is_current(at)]


def select_as_of(facts: list[TemporalFact], at: float) -> list[TemporalFact]:
    """Facts believed at system time ``at`` — the audit question.

    Deliberately uses system time only: asking "what did we believe last week"
    must not be contaminated by facts we learned since, including the knowledge
    that an earlier belief was later corrected.
    """
    return [f for f in facts if f.was_believed_at(at)]


def find_superseded_by(facts: list[TemporalFact], record_id: str) -> TemporalFact | None:
    """Follow the supersession chain one step forward, or None at the head."""
    for f in facts:
        if f.record_id == record_id and f.superseded_by:
            for cand in facts:
                if cand.record_id == f.superseded_by:
                    return cand
    return None


# --------------------------------------------------------------------------- #
# Event time: occurs_at
# --------------------------------------------------------------------------- #
#
# ``valid_at``/``invalid_at`` describe a fact that holds over a span — "worked at
# RUCHI from Aug to Nov 2025". An *event* is different: "dentist at 5pm" is true
# at an instant, not over a range. Before this, the store had no way to represent
# that, so a reminder was indistinguishable from a preference.
#
# Parsing is deliberately conservative. It extracts what is explicitly stated and
# returns None otherwise — a wrong reminder time is worse than no reminder, so
# ambiguity is reported as absent rather than guessed at. Relative expressions
# ("tomorrow", "next Monday") resolve against a caller-supplied reference so the
# same text parsed twice does not drift.

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def parse_occurs_at(text: str, reference: datetime | None = None) -> float | None:
    """Extract the instant an event occurs, or None when not explicitly stated.

    Handles, in priority order:
      * ISO dates / datetimes — ``2026-10-05``, ``2026-10-05T17:00``
      * ``5 October 2026`` / ``October 5 2026``, with optional ``at 5pm``
      * ``on 5/10/2026`` (day-first, matching the owner's locale)
      * relative day words — today / tomorrow / yesterday
      * ``next <weekday>`` / ``this <weekday>``

    Returns epoch seconds. A date with no time is midnight **local-naive**
    treated as UTC start-of-day, which is documented behaviour rather than an
    accident.
    """
    import re

    if not text:
        return None

    ref = reference or datetime.now(UTC)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    low = re.sub(r"\s+", " ", text).strip().lower()

    # Time-of-day suffix: "at 5pm", "at 17:30", "at 9 am".
    def _time_of_day(s: str) -> tuple[int, int] | None:
        m = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", s)
        if not m:
            return None
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        mer = m.group(3)
        if mer == "pm" and hour < 12:
            hour += 12
        if mer == "am" and hour == 12:
            hour = 0
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return hour, minute

    tod = _time_of_day(low)

    def _build(y: int, mo: int, d: int) -> float | None:
        hh, mm = tod if tod else (0, 0)
        try:
            return datetime(y, mo, d, hh, mm, tzinfo=UTC).timestamp()
        except ValueError:
            return None

    # ISO: 2026-10-05 or 2026-10-05T17:00
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})(?:[t ](\d{2}):(\d{2}))?", low)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if m.group(4):
            try:
                return datetime(y, mo, d, int(m.group(4)), int(m.group(5)), tzinfo=UTC).timestamp()
            except ValueError:
                return None
        return _build(y, mo, d)

    # "5 october 2026" / "5 oct 2026"
    m = re.search(r"\b(\d{1,2})\s+([a-z]{3,9})\.?\s+(\d{4})\b", low)
    if m and m.group(2)[:3] in _MONTHS:
        return _build(int(m.group(3)), _MONTHS[m.group(2)[:3]], int(m.group(1)))

    # "october 5 2026" / "oct 5, 2026"
    m = re.search(r"\b([a-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b", low)
    if m and m.group(1)[:3] in _MONTHS:
        return _build(int(m.group(3)), _MONTHS[m.group(1)[:3]], int(m.group(2)))

    # "on 5/10/2026" written as 5/10/2026 — day-first.
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", low)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            d, mo = mo, d  # tolerate month-first input
        return _build(y, mo, d)

    # "5 october" / "october 5" with no year — the next occurrence.
    m = re.search(r"\b(\d{1,2})\s+([a-z]{3,9})\.?\b", low)
    if m and m.group(2)[:3] in _MONTHS:
        mo, d = _MONTHS[m.group(2)[:3]], int(m.group(1))
        y = ref.year
        stamp = _build(y, mo, d)
        if stamp is not None and stamp < ref.timestamp():
            stamp = _build(y + 1, mo, d)
        return stamp

    m = re.search(r"\b([a-z]{3,9})\.?\s+(\d{1,2})\b", low)
    if m and m.group(1)[:3] in _MONTHS:
        mo, d = _MONTHS[m.group(1)[:3]], int(m.group(2))
        y = ref.year
        stamp = _build(y, mo, d)
        if stamp is not None and stamp < ref.timestamp():
            stamp = _build(y + 1, mo, d)
        return stamp

    # Relative day words.
    base = datetime(ref.year, ref.month, ref.day, tzinfo=UTC)
    for word, delta in (("today", 0), ("tonight", 0), ("tomorrow", 1), ("yesterday", -1)):
        if re.search(rf"\b{word}\b", low):
            day = base + timedelta(days=delta)
            hh, mm = tod if tod else (0, 0)
            return day.replace(hour=hh, minute=mm).timestamp()

    # next <weekday> / this <weekday>
    m = re.search(r"\b(next|this)\s+([a-z]+day)\b", low)
    if m and m.group(2) in _WEEKDAYS:
        target = _WEEKDAYS[m.group(2)]
        ahead = (target - base.weekday()) % 7
        if ahead == 0 or m.group(1) == "next":
            ahead = ahead or 7
        day = base + timedelta(days=ahead)
        hh, mm = tod if tod else (0, 0)
        return day.replace(hour=hh, minute=mm).timestamp()

    # A bare time with no date ("meeting at 5pm") has no anchor, so it is not a
    # date. Return None rather than inventing today.
    return None


def has_occurred(occurs_at: float | None, at: float | None = None) -> bool:
    """Whether an event's moment has already passed."""
    if occurs_at is None:
        return False
    now = at if at is not None else datetime.now(UTC).timestamp()
    return occurs_at <= now


def upcoming(
    events: list[tuple[str, float | None]], at: float | None = None
) -> list[tuple[str, float]]:
    """Events that have not happened yet, soonest first.

    Entries with no parseable time are dropped: an undated item cannot be
    scheduled and must not silently appear at the top of a list.
    """
    now = at if at is not None else datetime.now(UTC).timestamp()
    dated = [(rid, ts) for rid, ts in events if ts is not None]
    return sorted((e for e in dated if e[1] > now), key=lambda e: e[1])


def format_occurs_at(occurs_at: float | None, tz_offset_hours: float = 5.75) -> str:
    """Render an event time in the owner's local zone (default +05:45, Nepal).

    Stored as epoch UTC; displayed in local time so a reminder reads correctly.
    """
    if occurs_at is None:
        return "(no time)"
    tz = timezone(timedelta(hours=tz_offset_hours))
    return datetime.fromtimestamp(occurs_at, tz).strftime("%Y-%m-%d %H:%M %Z%z")
