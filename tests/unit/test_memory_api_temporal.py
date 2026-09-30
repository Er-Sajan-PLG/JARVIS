"""The memory API must expose temporal fields (ADR-015).

Regression: the store held valid_at/invalid_at but ``/api/memory`` serialized
only five hand-picked keys, so an ended employment came back over HTTP looking
exactly like a current one. Same class of bug as the earlier ``type: None``
drop — a hand-written serializer drifting from the domain object.

These tests are hermetic. They drive the real route through
``fastapi.testclient.TestClient`` -- the same route ``app.main:app`` mounts --
and replace the one boundary that leaves the process: ``bootstrap_system``, the
composition root the handler calls to reach the store. The records are built
here rather than read from ``data/memories.json``, so what is asserted is the
SERIALIZER's contract (does ``/api/memory`` emit the ADR-015 fields, and can an
ended fact be told from a current one) and not the contents of the owner's
personal store — that is a different suite, ``tests/data/``.

It previously fetched ``http://localhost:8000/api/memory`` with urllib and
called ``pytest.skip("server not running on :8000")`` when nothing was
listening, so in the gate (and in any fresh clone) it asserted nothing at all
while still reporting green.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.adapters.web import router as web_router_module
from app.memory.schema import Memory

TEMPORAL_KEYS = ("valid_at", "invalid_at", "expired_at", "occurs_at")

# Event time for the pair below: one employment that ended in Nov 2025, one fact
# that is still current. Told apart only by ``invalid_at``.
ENDED_VALID_AT = 1754006400.0  # 2025-08-01 — became true
ENDED_INVALID_AT = 1761955200.0  # 2025-11-01 — stopped being true
CREATED_AT = 1756684800.0  # 2025-09-01 — when the store learned either


def _memory(**overrides: Any) -> Memory:
    """The real domain object, so the serializer sees exactly what it sees live."""
    fields: dict[str, Any] = {
        "category": "profession",
        "memory_type": "work_period",
        "value": "Civil Engineer — ACME Corporation",
        "created_at": CREATED_AT,
    }
    fields.update(overrides)
    return Memory(**fields)


ENDED = _memory(
    value="Civil Engineer — ACME Corporation, Aug 2025 to Nov 2025",
    valid_at=ENDED_VALID_AT,
    invalid_at=ENDED_INVALID_AT,
)
CURRENT = _memory(
    category="identity",
    memory_type="location",
    value="Lives in Springfield",
)


class _StubManager:
    def __init__(self, records: list[Memory]) -> None:
        self._records = records

    def get_all(self) -> list[Memory]:
        return list(self._records)


class _StubMemoryService:
    def __init__(self, records: list[Memory]) -> None:
        self._manager = _StubManager(records)


class _StubContainer:
    """Only the surface ``list_memories`` touches, with the store edge removed."""

    def __init__(self, records: list[Memory]) -> None:
        self.memory_service = _StubMemoryService(records)


@pytest.fixture()
def records() -> list[Memory]:
    return [ENDED, CURRENT]


@pytest.fixture()
def client(records: list[Memory], monkeypatch: pytest.MonkeyPatch, api_key_env: str) -> TestClient:
    """The real app, with the store swapped for the records under test."""
    stub = _StubContainer(records)
    monkeypatch.setattr(web_router_module, "bootstrap_system", lambda *a, **k: stub)

    from app.main import app

    with TestClient(app) as c:
        c.headers["Authorization"] = f"Bearer {api_key_env}"
        yield c


@pytest.fixture()
def memories(client: TestClient) -> list[dict]:
    """The records exactly as ``GET /api/memory`` returns them."""
    response = client.get("/api/memory")
    assert response.status_code == 200, response.text
    return response.json()["memories"]


def test_api_exposes_temporal_fields(memories: list[dict]) -> None:
    assert memories, "API returned no memories"
    for m in memories:
        for key in TEMPORAL_KEYS:
            assert key in m, f"{key!r} missing from API record {m.get('value')!r}"


def test_ended_fact_is_distinguishable_over_the_api(memories: list[dict]) -> None:
    """An ended fact must carry a date; a current one must not."""
    ended = [m for m in memories if m.get("invalid_at")]
    assert ended, "expected at least one ended fact in the response"
    # The owner-visible property: an ended record carries a date, not None.
    for m in ended:
        assert m["invalid_at"], f"{m['value'][:40]!r} ended but invalid_at is falsy"

    current = [m for m in memories if not m.get("invalid_at")]
    assert current, "expected at least one still-current fact in the response"
    assert all(m["invalid_at"] is None for m in current), (
        "a still-current fact came back with an end date, so an ended fact is "
        f"again indistinguishable from a current one: {current}"
    )


def test_serializer_source_lists_temporal_fields() -> None:
    """Guard the source itself so CI catches the drop without a live server."""
    src = (
        Path(__file__).resolve().parents[2] / "app" / "adapters" / "web" / "router.py"
    ).read_text()
    for key in TEMPORAL_KEYS:
        assert f'"{key}"' in src, f"/api/memory serializer no longer emits {key!r}"
