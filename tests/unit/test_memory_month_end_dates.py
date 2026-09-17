"""Month-granularity periods must resolve END dates to the last day.

Regression: the first temporal migration mapped "Aug 2025 to Nov 2025" to
``2025-11-01``. That claims the job ended on the 1st of November, understating
employment by a month and making JARVIS report the wrong leaving date to the
owner. "to Nov 2025" means "through the end of November".

The distinction that matters: a month-granularity START is the 1st (when it
began), a month-granularity END is the last day (when it finished).
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrate_memory_temporal.py"


def _load():
    spec = importlib.util.spec_from_file_location("_migrate_temporal", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mig():
    return _load()


def _d(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d") if ts else None


def test_slash_period_end_is_month_end(mig) -> None:
    """The exact REV 7.0 shape that was wrong."""
    s, e = mig._derive_event_time(
        "Civil Engineer — RUCHI DEVELOPER PVT. LTD. (08/2025 - 11/2025)"
    )
    assert _d(s) == "2025-08-01"
    assert _d(e) == "2025-11-30", "end must be the last day of November"


def test_slash_period_end_handles_february(mig) -> None:
    """February's length must come from the calendar, not a hardcoded 30/31."""
    _, e = mig._derive_event_time("Role (01/2026 - 02/2026)")
    assert _d(e) == "2026-02-28"


def test_slash_period_end_handles_leap_february(mig) -> None:
    _, e = mig._derive_event_time("Role (01/2024 - 02/2024)")
    assert _d(e) == "2024-02-29"


def test_word_month_period_end_is_month_end(mig) -> None:
    _, e = mig._derive_event_time("Roadshow, Aug 2024 to Nov 2025")
    assert _d(e) == "2025-11-30"


def test_year_range_end_is_year_end(mig) -> None:
    """A degree ending '2023' ends in December, not January."""
    s, e = mig._derive_event_time("BE Civil (2018-2023)")
    assert _d(s) == "2018-01-01"
    assert _d(e) == "2023-12-31"


def test_end_is_never_before_start(mig) -> None:
    """Sanity: a same-month period must not invert."""
    s, e = mig._derive_event_time("Intern (05/2026 - 05/2026)")
    assert s is not None and e is not None and e >= s


def test_month_end_helper_is_calendar_correct(mig) -> None:
    assert _d(mig._month_end(2026, 1)) == "2026-01-31"
    assert _d(mig._month_end(2026, 4)) == "2026-04-30"
    assert _d(mig._month_end(2026, 12)) == "2026-12-31"
    assert _d(mig._month_end(2024, 2)) == "2024-02-29"
    assert _d(mig._month_end(2025, 2)) == "2025-02-28"


def test_no_date_returns_none(mig) -> None:
    assert mig._derive_event_time("Likes pizza") == (None, None)


def test_live_store_employment_dates_match_the_cv() -> None:
    """The owner-visible consequence: stored end dates must equal CV REV 7.0."""
    store = Path(__file__).resolve().parents[2] / "data" / "memories.json"
    if not store.exists():
        pytest.skip("memory store not present")

    import json

    ms = json.loads(store.read_text())["memories"]
    employment = [m for m in ms if m.get("invalid_at") and "RUCHI" in m["value"]]
    assert employment, "no RUCHI record found to check"
    for m in employment:
        assert _d(m["invalid_at"]) == "2025-11-30", (
            f"{m['value'][:50]!r} ended {_d(m['invalid_at'])}, CV says Nov 2025"
        )
