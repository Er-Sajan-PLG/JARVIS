"""The memory write path must not accumulate duplicates or store probe junk.

Regression for a real audit finding: ``data/memories.json`` held 492 records
that collapsed to 49 unique values (90% duplication), including 372 identical
copies of a bogus ``user_name`` and ~49 verbatim chat probes ("ping",
"default ok", "reply with exactly: ping").

Root cause: ``MemoryService.store_memory()`` — the only path the web chat uses —
called ``MemoryStore.add()``, a bare ``list.append`` with no duplicate check,
and never invoked the near-duplicate detector that already existed in
``app/memory/dedup.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.memory.service import MemoryService, _is_storable


@dataclass
class _Row:
    """Stand-in for the manager's Memory row object."""

    id: str
    category: str
    value: str
    memory_type: str
    access_count: int = 0


class _FakeStore:
    def __init__(self) -> None:
        self.rows: list[_Row] = []
        self.saves = 0

    def get_all(self) -> list[_Row]:
        return list(self.rows)

    def add(self, memory: _Row) -> _Row:
        self.rows.append(memory)
        return memory

    def save(self) -> None:
        self.saves += 1


class _FakeManager:
    """Duck-typed MemoryManager — only the two members MemoryService touches."""

    def __init__(self) -> None:
        self._store = _FakeStore()

    def store(self, fact: dict[str, Any]) -> _Row:
        row = _Row(
            id=fact["id"],
            category=fact["category"],
            value=fact["value"],
            memory_type=fact["type"],
        )
        self._store.add(row)
        return row


# ── junk screening ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", [
    "ping", "PING", "pong", "ok", "hello", "hi", "test", "testing",
    "default ok", "live ok", "nvidia ok", "say ok",
    "reply with exactly: ping", "reply with exactly: nvidia ok",
    "test memory for session",
])
def test_probe_values_are_not_storable(value):
    """Chat probes are not facts. Storing them is what filled the store."""
    assert _is_storable(value) is False


def test_pipeline_log_text_is_not_storable():
    """The extractor once swallowed its own log line as content."""
    assert _is_storable("goals [memory] stored: state → working on jarvis") is False


@pytest.mark.parametrize("value", [
    "Jane Doe",
    "User likes pizza",
    "a history student at Example University in Freedonia",
    "first-principles explanations over surface-level tutorials",
    "Solid-state batteries replace the liquid electrolyte.",
])
def test_real_memories_are_storable(value):
    """The guard must not throw away genuine content."""
    assert _is_storable(value) is True


def test_short_and_empty_values_rejected():
    assert _is_storable("") is False
    assert _is_storable("   ") is False
    assert _is_storable("x") is False


# ── duplicate suppression ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_storing_the_same_value_twice_does_not_duplicate():
    """The exact failure that produced 372 copies of one value."""
    svc = MemoryService(manager=_FakeManager())

    for _ in range(25):
        await svc.store_memory(key="user_name", value="Alice", category="identity")

    rows = svc._manager._store.get_all()
    assert len(rows) == 1, f"expected 1 row, got {len(rows)}"
    assert getattr(rows[0], "access_count", 0) == 24, "repeats should bump access_count"


@pytest.mark.asyncio
async def test_duplicate_check_ignores_whitespace_and_case():
    """'User likes pizza' and 'user  likes   PIZZA' are the same memory."""
    svc = MemoryService(manager=_FakeManager())
    await svc.store_memory(key="k", value="User likes pizza", category="preferences")
    await svc.store_memory(key="k", value="  user   LIKES pizza  ", category="preferences")
    assert len(svc._manager._store.get_all()) == 1


@pytest.mark.asyncio
async def test_different_values_still_store_separately():
    """Dedup must not collapse distinct memories."""
    svc = MemoryService(manager=_FakeManager())
    await svc.store_memory(key="k", value="User likes pizza", category="preferences")
    await svc.store_memory(key="k", value="User likes coffee", category="preferences")
    assert len(svc._manager._store.get_all()) == 2


@pytest.mark.asyncio
async def test_discovered_name_is_persisted_at_most_once():
    """Minimal end-to-end: a name asserted on many turns yields one record."""
    svc = MemoryService(manager=_FakeManager())
    for _ in range(5):
        await svc.store_memory(key="name", value="Jane Doe", category="identity")
    rows = svc._manager._store.get_all()
    assert len(rows) == 1
    assert getattr(rows[0], "value", "") == "Jane Doe"


@pytest.mark.asyncio
async def test_junk_is_never_written_to_the_store():
    """A probe value must not create a row at all."""
    svc = MemoryService(manager=_FakeManager())
    for probe in ("ping", "default ok", "test"):
        await svc.store_memory(key="user_1", value=probe, category="conversation")
    assert svc._manager._store.get_all() == []
