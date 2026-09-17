"""Date and schedule memories must be representable.

Regression for the gap found when the owner asked for "meeting at x o'clock,
birthday, event date, working period" support: the rule set had 22 entries and
NOT ONE captured a point or range in time. Meetings, birthdays, deadlines,
events and work periods simply could not be stored.

`MemoryItem` carries `expires_at` but nothing carries `occurs_at`, so a date is
stored as part of the value text. That is a known limitation, asserted here so
it is visible rather than assumed away.
"""

from __future__ import annotations

import pytest

from app.memory.rules import RULES


def _types() -> set[str]:
    return {str(r.get("type")) for r in RULES}


def _by_type(mtype: str) -> dict:
    for r in RULES:
        if r.get("type") == mtype:
            return r
    raise AssertionError(f"no rule with type {mtype!r}")


# ── the specific categories the owner asked for ─────────────────────────────


@pytest.mark.parametrize("mtype", ["birthday", "meeting", "deadline", "event",
                                   "appointment", "recurring", "work_period", "key_date"])
def test_schedule_types_exist(mtype):
    """Every date-bearing category the owner listed must have a rule."""
    assert mtype in _types(), f"missing schedule type: {mtype}"


def test_birthday_rule_recognises_the_obvious_phrasings():
    triggers = " ".join(_by_type("birthday")["triggers"])
    for phrase in ("my birthday is", "born on"):
        assert phrase in triggers


def test_meeting_rule_covers_a_clock_time():
    """'meeting at 5 o'clock' is the exact case the owner named."""
    triggers = " ".join(_by_type("meeting")["triggers"])
    assert "meeting at " in triggers


def test_work_period_is_its_own_type():
    """Employment ranges are not the same thing as a current job title."""
    assert "work_period" in _types()
    assert "job_title" in _types()
    # They must be genuinely separate rules, not one rule relabelled.
    assert _by_type("work_period") is not _by_type("job_title")
    triggers = " ".join(_by_type("work_period")["triggers"])
    assert "worked at " in triggers or "working at " in triggers


def test_recurring_rule_handles_weekly_commitments():
    triggers = " ".join(_by_type("recurring")["triggers"])
    assert "every monday" in triggers


# ── direction: aim vs mission vs vision ─────────────────────────────────────


def test_vision_rules_are_distinct_from_goals():
    """Long-range direction must not collapse into near-term goals."""
    assert "vision" in _types()
    assert "mission" in _types()
    # goals still exist separately
    assert {"desire", "objective", "aspiration"} <= _types()


def test_relationships_are_captured():
    """People matter for an assistant that is supposed to know the user."""
    assert "person" in _types()


# ── the whole rule set stays coherent ───────────────────────────────────────


def test_every_rule_is_well_formed():
    """A malformed rule silently never matches, so validate the shape."""
    for i, r in enumerate(RULES):
        assert r.get("category"), f"rule {i} has no category"
        assert r.get("type"), f"rule {i} has no type"
        assert r.get("behavior") == "append", f"rule {i} has unexpected behavior"
        triggers = r.get("triggers")
        assert isinstance(triggers, list) and triggers, f"rule {i} has no triggers"
        for t in triggers:
            assert isinstance(t, str) and t.strip(), f"rule {i} has a blank trigger"
            assert t == t.lower(), f"rule {i} trigger {t!r} must be lowercase to match"


def test_rule_types_are_unique_per_category():
    """Two rules with the same (category, type) would shadow each other."""
    seen = set()
    for r in RULES:
        key = (r["category"], r["type"])
        assert key not in seen, f"duplicate rule for {key}"
        seen.add(key)


def test_schedule_category_is_populated():
    """The category that did not exist before must now carry real rules."""
    sched = [r for r in RULES if r.get("category") == "schedule"]
    assert len(sched) >= 8, f"expected the schedule rules, found {len(sched)}"


def test_known_limitation_no_occurs_at_field():
    """Documents the honest gap: dates live in the value text, not a field.

    If `occurs_at` is ever added to MemoryItem, this test should be updated and
    the date rules tightened to populate it.
    """
    from app.domain.memory import MemoryItem

    fields = set(MemoryItem.__dataclass_fields__)
    assert "expires_at" in fields
    assert "occurs_at" not in fields, (
        "occurs_at now exists — populate it from the schedule rules and "
        "remove this limitation note"
    )