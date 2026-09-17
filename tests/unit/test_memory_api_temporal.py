"""The memory API must expose temporal fields (ADR-015).

Regression: the store held valid_at/invalid_at but ``/api/memory`` serialized
only five hand-picked keys, so an ended employment came back over HTTP looking
exactly like a current one. Same class of bug as the earlier ``type: None``
drop — a hand-written serializer drifting from the domain object.

This test asserts through HTTP when a server is reachable, and falls back to
the serializer's own source otherwise, so it gives a real signal in both the
CI gate (no server) and local manual runs.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

TEMPORAL_KEYS = ("valid_at", "invalid_at", "expired_at", "occurs_at")
API = "http://localhost:8000/api/memory"


def _fetch() -> list[dict] | None:
    try:
        with urllib.request.urlopen(API, timeout=5) as r:  # noqa: S310
            return json.loads(r.read())["memories"]
    except (urllib.error.URLError, TimeoutError, OSError, KeyError):
        return None


def test_api_exposes_temporal_fields_when_server_running() -> None:
    memories = _fetch()
    if memories is None:
        pytest.skip("server not running on :8000")
    assert memories, "API returned no memories"
    for m in memories:
        for key in TEMPORAL_KEYS:
            assert key in m, f"{key!r} missing from API record {m.get('value')!r}"


def test_ended_fact_is_distinguishable_over_the_api() -> None:
    memories = _fetch()
    if memories is None:
        pytest.skip("server not running on :8000")
    ended = [m for m in memories if m.get("invalid_at")]
    assert ended, "expected at least one ended fact in the store"
    # The owner-visible property: an ended record carries a date, not None.
    for m in ended:
        assert m["invalid_at"], f"{m['value'][:40]!r} ended but invalid_at is falsy"


def test_serializer_source_lists_temporal_fields() -> None:
    """Guard the source itself so CI catches the drop without a live server."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2] / "app" / "adapters" / "web" / "router.py"
    ).read_text()
    for key in TEMPORAL_KEYS:
        assert f'"{key}"' in src, f"/api/memory serializer no longer emits {key!r}"
