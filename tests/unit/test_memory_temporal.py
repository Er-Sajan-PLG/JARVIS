"""Bi-temporal memory: two clocks, invalidate-not-delete.

Design is ADR-015. The behaviours under test are the ones whose absence caused
real data loss on 2026-09-15: corrections overwrote prior facts, so the store
could not answer "what did we believe before the correction" and a mistaken
correction was unrecoverable.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.memory.temporal import (
    TemporalFact,
    close_interval,
    find_superseded_by,
    is_valid_at,
    select_as_of,
    select_current,
)


def _epoch(y: int, m: int, d: int = 1) -> float:
    return datetime(y, m, d, tzinfo=UTC).timestamp()


# The real case: a job that ended must not read as current.
def test_ended_employment_is_not_current() -> None:
    ru = TemporalFact(
        record_id="ruchi",
        valid_at=_epoch(2025, 8),
        invalid_at=_epoch(2025, 11),
        created_at=_epoch(2026, 9, 15),
    )
    assert not ru.is_current(at=_epoch(2026, 9, 15))


def test_open_ended_fact_is_current() -> None:
    pref = TemporalFact(record_id="pref", created_at=_epoch(2026, 9, 15))
    assert pref.is_current(at=_epoch(2026, 9, 16))


def test_fact_not_yet_valid_is_not_current() -> None:
    """A scheduled event in the future is not yet true now."""
    future = TemporalFact(record_id="mtg", valid_at=_epoch(2027, 1), created_at=_epoch(2026, 9, 15))
    assert not future.is_current(at=_epoch(2026, 9, 15))
    assert future.is_current(at=_epoch(2027, 6))


# --- the two clocks are independent -------------------------------------------


def test_world_time_and_system_time_answer_different_questions() -> None:
    """A job that ended in Nov 2025, corrected in Sep 2026.

    Event time says the world changed in Nov 2025. System time says we did not
    learn about it until Sep 2026. A single clock cannot express both.
    """
    f = TemporalFact(
        record_id="ruchi",
        valid_at=_epoch(2025, 8),
        invalid_at=_epoch(2025, 11),
        created_at=_epoch(2026, 9, 15),
    )
    # In the world: not true after Nov 2025.
    assert not is_valid_at(f, _epoch(2026, 1))
    assert is_valid_at(f, _epoch(2025, 9))
    # In the store: not even known until Sep 2026.
    assert not f.was_believed_at(_epoch(2026, 1))


def test_as_of_ignores_facts_learned_later() -> None:
    """The audit question must not be contaminated by later knowledge.

    Asking "what did we believe in June" must exclude a fact recorded in
    September — including the fact that an earlier belief was corrected.
    """
    believed_then = TemporalFact(record_id="old", created_at=_epoch(2026, 6))
    learned_later = TemporalFact(record_id="new", created_at=_epoch(2026, 9), supersedes="old")

    as_of_june = select_as_of([believed_then, learned_later], _epoch(2026, 7))
    assert [f.record_id for f in as_of_june] == ["old"]

    now = select_as_of([believed_then, learned_later], _epoch(2026, 10))
    assert {f.record_id for f in now} == {"old", "new"}


# --- invalidate, never delete -------------------------------------------------


def test_correction_closes_old_interval_without_deleting() -> None:
    old = TemporalFact(
        record_id="old", valid_at=_epoch(2024, 1), created_at=_epoch(2024, 1), source="linkedin"
    )
    new = TemporalFact(
        record_id="new", valid_at=_epoch(2025, 8), created_at=_epoch(2026, 9, 15), source="cv"
    )

    res = close_interval(old, new, now=_epoch(2026, 9, 15), reason="superseded by CV")

    assert res.applied
    assert res.old_id == "old" and res.new_id == "new"
    # World time: the old fact stopped being true when the new one began.
    assert res.invalid_at == _epoch(2025, 8)
    # System time: we learned it now.
    assert res.expired_at == _epoch(2026, 9, 15)


def test_invalidated_fact_still_readable_for_as_of() -> None:
    """The whole point: the superseded fact remains answerable as history."""
    old = TemporalFact(record_id="old", valid_at=_epoch(2024, 1), created_at=_epoch(2024, 1))
    new = TemporalFact(record_id="new", valid_at=_epoch(2025, 8), created_at=_epoch(2026, 9, 15))

    res = close_interval(old, new, now=_epoch(2026, 9, 15))
    retired = TemporalFact(
        record_id=old.record_id,
        valid_at=old.valid_at,
        invalid_at=res.invalid_at,
        created_at=old.created_at,
        expired_at=res.expired_at,
        superseded_by=new.record_id,
    )

    # Not current any more...
    assert not retired.is_current(at=_epoch(2026, 9, 16))
    # ...but still readable as what we believed back then.
    assert retired.was_believed_at(_epoch(2025, 1))
    assert select_as_of([retired], _epoch(2025, 1)) == [retired]


def test_disjoint_periods_are_not_a_correction() -> None:
    """'Ran 5 miles Tuesday' must not invalidate 'ran 3 miles Wednesday'."""
    tue = TemporalFact(
        record_id="tue", valid_at=_epoch(2026, 9, 15), invalid_at=_epoch(2026, 9, 16)
    )
    wed = TemporalFact(
        record_id="wed", valid_at=_epoch(2026, 9, 16), invalid_at=_epoch(2026, 9, 17)
    )

    res = close_interval(tue, wed, now=_epoch(2026, 9, 20))
    assert not res.applied
    assert "non-overlapping" in res.reason


def test_out_of_order_ingestion_is_clamped_not_reversed() -> None:
    """A late-arriving older fact must not push the interval backwards."""
    old = TemporalFact(record_id="old", valid_at=_epoch(2026, 1), created_at=_epoch(2026, 1))
    late = TemporalFact(record_id="late", valid_at=_epoch(2020, 1), created_at=_epoch(2026, 9, 15))

    res = close_interval(old, late, now=_epoch(2026, 9, 15))
    # Clamped to the old fact's own start — never before it was true.
    assert old.valid_at is not None
    assert res.invalid_at >= old.valid_at
    assert any("clamped" in n for n in res.notes)


def test_supersession_chain_is_followable() -> None:
    facts = [
        TemporalFact(record_id="a", superseded_by="b", created_at=_epoch(2026, 1)),
        TemporalFact(record_id="b", superseded_by="c", created_at=_epoch(2026, 5)),
        TemporalFact(record_id="c", created_at=_epoch(2026, 9)),
    ]
    b = find_superseded_by(facts, "a")
    c = find_superseded_by(facts, "b")
    assert b is not None and b.record_id == "b"
    assert c is not None and c.record_id == "c"
    assert find_superseded_by(facts, "c") is None


# --- determinism --------------------------------------------------------------


def test_interval_arithmetic_does_not_need_a_model() -> None:
    """The reason code owns this: a model must never be asked to order dates."""
    old = TemporalFact(record_id="o", valid_at=_epoch(2025, 1), created_at=_epoch(2025, 1))
    new = TemporalFact(record_id="n", valid_at=_epoch(2025, 6), created_at=_epoch(2026, 9, 15))

    first = close_interval(old, new, now=_epoch(2026, 9, 15))
    second = close_interval(old, new, now=_epoch(2026, 9, 15))
    assert first.invalid_at == second.invalid_at
    assert first.expired_at == second.expired_at


def test_select_current_excludes_retired_facts() -> None:
    facts = [
        TemporalFact(record_id="live", created_at=_epoch(2026, 9, 15)),
        TemporalFact(
            record_id="dead", created_at=_epoch(2025, 1), expired_at=_epoch(2026, 9, 15)
        ),
    ]
    current = select_current(facts, at=_epoch(2026, 9, 16))
    assert [f.record_id for f in current] == ["live"]


def test_from_dict_reads_iso_timestamps_and_epochs() -> None:
    iso = TemporalFact.from_dict({"id": "x", "valid_at": "2025-08-01T00:00:00Z"})
    assert iso.valid_at == _epoch(2025, 8)
    epoch = TemporalFact.from_dict({"id": "y", "valid_at": 1700000000})
    assert epoch.valid_at == 1700000000.0
    assert TemporalFact.from_dict({"id": "z"}).valid_at is None
    assert TemporalFact.from_dict({"id": "z", "valid_at": "not-a-date"}).valid_at is None


def test_real_store_facts_carry_both_clocks() -> None:
    """Every record in the live store must expose the ADR-015 fields."""
    import json
    from pathlib import Path

    store = Path(__file__).resolve().parents[2] / "data" / "memories.json"
    if not store.exists():
        pytest.skip("memory store not present")

    for m in json.loads(store.read_text())["memories"]:
        assert "created_at" in m, f"missing system clock on {m.get('value')!r}"
        assert "valid_at" in m, f"missing event clock on {m.get('value')!r}"
        # Reading each one through the temporal model must not raise.
        TemporalFact.from_dict(m)


def test_ended_employment_in_real_store_reads_as_not_current() -> None:
    """Regression for the actual data: both CV jobs ended in Nov 2025."""
    import json
    from pathlib import Path

    store = Path(__file__).resolve().parents[2] / "data" / "memories.json"
    if not store.exists():
        pytest.skip("memory store not present")

    facts = [TemporalFact.from_dict(m) for m in json.loads(store.read_text())["memories"]]
    closed = [f for f in facts if f.valid_at and f.invalid_at]
    assert closed, "no facts carry a closed validity window"
    # All five derived intervals are past events and must read as not current.
    for f in closed:
        assert not f.is_current(), f"{f.record_id} still reads as current"
