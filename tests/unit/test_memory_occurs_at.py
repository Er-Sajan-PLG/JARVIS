"""occurs_at: an event's moment, distinct from a fact's validity interval.

The store could represent "worked at RUCHI from Aug to Nov 2025" (a span) but
not "dentist at 5pm on 5 October" (an instant). A reminder was therefore
indistinguishable from a preference.

Parsing is deliberately conservative. A wrong reminder time is worse than no
reminder, so anything not explicitly stated returns None rather than a guess.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.memory.temporal import format_occurs_at, has_occurred, parse_occurs_at, upcoming

REF = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def _fmt(ts: float | None) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d %H:%M") if ts else "None"


# --- explicit dates -----------------------------------------------------------


def test_iso_date() -> None:
    assert _fmt(parse_occurs_at("meeting on 2026-10-05", REF)) == "2026-10-05 00:00"


def test_iso_datetime_with_time() -> None:
    assert _fmt(parse_occurs_at("standup 2026-10-05T17:00", REF)) == "2026-10-05 17:00"


def test_day_month_year_with_time() -> None:
    got = parse_occurs_at("birthday party on 5 October 2026 at 7pm", REF)
    assert _fmt(got) == "2026-10-05 19:00"


def test_month_day_year() -> None:
    assert _fmt(parse_occurs_at("Viva on October 5, 2026", REF)) == "2026-10-05 00:00"


def test_abbreviated_month() -> None:
    assert _fmt(parse_occurs_at("exam on 12 Nov 2026", REF)) == "2026-11-12 00:00"


def test_slash_date_is_day_first() -> None:
    """Owner's locale writes day/month/year; 5/10 is 5 October, not 10 May."""
    assert _fmt(parse_occurs_at("appointment on 5/10/2026", REF)) == "2026-10-05 00:00"


def test_noon_and_midnight_edge_cases() -> None:
    assert _fmt(parse_occurs_at("call on 2026-10-05 at 12pm", REF)) == "2026-10-05 12:00"
    assert _fmt(parse_occurs_at("call on 2026-10-05 at 12am", REF)) == "2026-10-05 00:00"


def test_24_hour_time() -> None:
    assert _fmt(parse_occurs_at("call on 2026-10-05 at 17:30", REF)) == "2026-10-05 17:30"


# --- relative dates -----------------------------------------------------------


def test_tomorrow_with_time() -> None:
    assert _fmt(parse_occurs_at("dentist tomorrow at 5pm", REF)) == "2026-09-16 17:00"


def test_today() -> None:
    assert _fmt(parse_occurs_at("call today at 3pm", REF)) == "2026-09-15 15:00"


def test_yesterday_is_in_the_past() -> None:
    got = parse_occurs_at("it was yesterday at 9am", REF)
    assert has_occurred(got, at=REF.timestamp())


def test_next_weekday() -> None:
    # 2026-09-15 is a Tuesday; next Friday is the 18th.
    assert _fmt(parse_occurs_at("review next friday at 10am", REF)) == "2026-09-18 10:00"


def test_month_without_year_rolls_forward() -> None:
    """'5 October' said in September means this year, not the past."""
    assert _fmt(parse_occurs_at("event on 5 October at 2pm", REF)) == "2026-10-05 14:00"


def test_month_without_year_already_passed_rolls_to_next_year() -> None:
    assert _fmt(parse_occurs_at("event on 5 March", REF)) == "2027-03-05 00:00"


# --- refusal: no guessing -----------------------------------------------------


def test_bare_time_has_no_date_and_returns_none() -> None:
    """'meeting at 5pm' has no anchor — inventing today would be a wrong reminder."""
    assert parse_occurs_at("meeting at 5pm", REF) is None


def test_no_date_at_all_returns_none() -> None:
    assert parse_occurs_at("I like pizza", REF) is None
    assert parse_occurs_at("", REF) is None


def test_invalid_date_returns_none() -> None:
    assert parse_occurs_at("event on 2026-02-31", REF) is None
    assert parse_occurs_at("event on 45/99/2026", REF) is None


def test_parse_is_deterministic_for_the_same_reference() -> None:
    """Relative text parsed against a fixed reference must not drift."""
    first = parse_occurs_at("tomorrow at 9am", REF)
    second = parse_occurs_at("tomorrow at 9am", REF)
    assert first == second


# --- occurred / upcoming ------------------------------------------------------


def test_has_occurred() -> None:
    past = parse_occurs_at("2026-01-01", REF)
    future = parse_occurs_at("2027-01-01", REF)
    assert has_occurred(past, at=REF.timestamp())
    assert not has_occurred(future, at=REF.timestamp())
    assert not has_occurred(None, at=REF.timestamp())


def test_upcoming_sorted_and_excludes_past_and_undated() -> None:
    events = [
        ("later", parse_occurs_at("2026-12-01", REF)),
        ("past", parse_occurs_at("2026-01-01", REF)),
        ("undated", None),
        ("sooner", parse_occurs_at("2026-10-01", REF)),
    ]
    got = [rid for rid, _ in upcoming(events, at=REF.timestamp())]
    assert got == ["sooner", "later"]


def test_format_uses_owner_timezone() -> None:
    """Nepal is +05:45 — a stored UTC instant must display shifted."""
    ts = parse_occurs_at("2026-10-05T12:00", REF)
    assert ts is not None
    assert "17:45" in format_occurs_at(ts)
    assert format_occurs_at(None) == "(no time)"


def test_birthday_parses_as_a_recurring_date() -> None:
    """A birthday is a date without a year; it must still yield a real moment."""
    got = parse_occurs_at("my birthday is 28 February", REF)
    assert got is not None
    assert datetime.fromtimestamp(got, UTC).month == 2
    assert datetime.fromtimestamp(got, UTC).day == 28
