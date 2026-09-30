"""Temporal fields must survive the store's save/load round-trip.

Regression risk: ``Memory.to_dict()`` enumerated its fields by hand, so any
field added to the dataclass but not to that method was silently dropped on the
next save. The ADR-015 temporal fields (valid_at, invalid_at, expired_at,
occurs_at, superseded_by, supersedes) would have vanished the first time the
server wrote the store — the same class of bug as the API dropping ``type``.

The round-trip is exercised against a store in ``tmp_path``, so the suite writes
nothing outside pytest's temporary directory. A test that read the developer's
live ``data/memories.json`` used to sit at the end of this file; it skipped
whenever that file was absent, so it measured nothing in a fresh clone or in CI.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.memory.schema import Memory
from app.memory.store import MemoryStore


def _temporal() -> Memory:
    return Memory(
        category="profession",
        memory_type="work_period",
        value="Civil Engineer — ACME Corporation, Aug 2025 to Nov 2025",
        valid_at=1754006400.0,
        invalid_at=1761955200.0,
        expired_at=1789000000.0,
        occurs_at=None,
        superseded_by="new12345",
        supersedes="old12345",
    )


def test_to_dict_includes_every_temporal_field() -> None:
    d = _temporal().to_dict()
    for key in (
        "valid_at",
        "invalid_at",
        "expired_at",
        "occurs_at",
        "superseded_by",
        "supersedes",
    ):
        assert key in d, f"to_dict() omits {key!r} — it would be lost on save"


def test_round_trip_preserves_temporal_values() -> None:
    original = _temporal()
    restored = Memory.from_dict(original.to_dict())
    assert restored.valid_at == original.valid_at
    assert restored.invalid_at == original.invalid_at
    assert restored.expired_at == original.expired_at
    assert restored.occurs_at == original.occurs_at
    assert restored.superseded_by == original.superseded_by
    assert restored.supersedes == original.supersedes


def test_occurs_at_round_trips_for_an_event() -> None:
    """An event's instant must survive too, not just a validity span."""
    event = Memory(
        category="schedule",
        memory_type="meeting",
        value="Dentist tomorrow at 5pm",
        occurs_at=1791500000.0,
    )
    assert Memory.from_dict(event.to_dict()).occurs_at == 1791500000.0


def test_store_save_preserves_temporal_fields(tmp_path: Path) -> None:
    """The real path: add to a store, save, reload from disk."""
    path = tmp_path / "memories.json"
    store = MemoryStore(path=path)
    store.add(_temporal())
    store.save()

    # Read the raw JSON, not the in-memory objects.
    on_disk = json.loads(path.read_text())["memories"][0]
    assert on_disk["valid_at"] == 1754006400.0
    assert on_disk["invalid_at"] == 1761955200.0
    assert on_disk["superseded_by"] == "new12345"

    # And a fresh store reading the file sees them.
    reloaded = MemoryStore(path=path).get_all()
    assert reloaded[0].valid_at == 1754006400.0
    assert reloaded[0].supersedes == "old12345"


def test_absent_temporal_fields_load_as_none() -> None:
    """Pre-migration records (no temporal keys) must still load."""
    legacy = {
        "id": "abc12345",
        "category": "preference",
        "type": "like",
        "value": "Likes pizza",
        "created_at": 1700000000.0,
        "updated_at": 1700000000.0,
    }
    m = Memory.from_dict(legacy)
    assert m.valid_at is None
    assert m.invalid_at is None
    assert m.expired_at is None
    assert m.occurs_at is None
    assert m.superseded_by is None
    assert m.value == "Likes pizza"
