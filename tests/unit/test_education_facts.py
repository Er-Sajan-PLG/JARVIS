"""Education facts must distinguish the university from the college.

The owner corrected this explicitly: "the main university is POKHARA UNIVERSITY
and the college studied is POKHARA ENGINEERING COLLEGE, set it up like that."

Before the fix the store held two competing, contradictory-looking degree
records — one naming Pokhara University, one naming Pokhara Engineering
College — with no way to tell whether they conflicted or described the same
education at two levels. They describe the same education: the college is where
he studied, the university awards the degree.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
import pytest

STORE = Path(__file__).resolve().parents[2] / "data" / "memories.json"


def _norm(v: object) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip().lower())


@pytest.fixture(scope="module")
def memories() -> list[dict]:
    if not STORE.exists():
        pytest.skip("memory store not present in this checkout")
    return json.loads(STORE.read_text())["memories"]


def _values(memories: list[dict]) -> list[str]:
    return [_norm(m.get("value")) for m in memories]


def test_university_is_pokhara_university(memories: list[dict]) -> None:
    """The awarding university must be recorded as Pokhara University."""
    hits = [v for v in _values(memories) if "pokhara university" in v]
    assert hits, "no memory records Pokhara University as the university"


def test_college_is_pokhara_engineering_college(memories: list[dict]) -> None:
    """The place of study must be recorded as Pokhara Engineering College."""
    hits = [v for v in _values(memories) if "pokhara engineering college" in v]
    assert hits, "no memory records Pokhara Engineering College"


def test_university_and_college_are_separate_facts(memories: list[dict]) -> None:
    """Both must exist as distinct typed entries, not one merged blob.

    If they were merged, a later correction to one would drag the other with
    it; keeping them typed separately lets each be corrected alone.
    """
    types = {m.get("type") for m in memories}
    assert "university" in types, "university is not stored under its own type"
    assert "college" in types, "college is not stored under its own type"


def test_api_exposes_the_fact_type_not_just_the_category(memories: list[dict]) -> None:
    """The API must report the fact type, not only a broad category.

    Regression: ``GET /api/memory`` returned only ``category`` ("education"),
    so a caller could not tell the university fact from the college fact. The
    endpoint read ``m.type``, but the domain object names the field
    ``memory_type`` — so every record came back with ``type: None``.
    """
    import urllib.request

    try:
        with urllib.request.urlopen("http://localhost:8000/api/memory", timeout=20) as r:
            payload = json.loads(r.read())
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"live server not reachable: {exc}")

    edu = [m for m in payload["memories"] if m.get("category") == "education"]
    assert edu, "no education records returned by the API"
    untyped = [m for m in edu if not m.get("type")]
    assert not untyped, (
        "API returned education records with no type, so the university and "
        f"college facts are indistinguishable: {untyped}"
    )
    types = {m["type"] for m in edu}
    assert "university" in types, f"university type missing from API: {types}"
    assert "college" in types, f"college type missing from API: {types}"


def test_no_memory_claims_he_studied_at_pokhara_university(memories: list[dict]) -> None:
    """He studied at the college — the university awards, it is not the campus.

    This is the specific confusion the owner was correcting.
    """
    offenders = [
        m.get("value")
        for m in memories
        if "studied at pokhara university" in _norm(m.get("value"))
    ]
    assert not offenders, f"memory claims he studied at Pokhara University: {offenders}"


def test_no_contradictory_duplicate_degree_records(memories: list[dict]) -> None:
    """There must be exactly one degree statement, not two competing ones."""
    degrees = [
        m for m in memories
        if m.get("type") == "degree"
        and ("pokhara" in _norm(m.get("value")) or "civil engineering" in _norm(m.get("value")))
    ]
    assert len(degrees) <= 1, (
        f"expected at most one Pokhara/civil degree record, found {len(degrees)}: "
        f"{[d.get('value') for d in degrees]}"
    )


def test_store_has_no_exact_duplicate_values(memories: list[dict]) -> None:
    """The store must stay deduplicated (492 records were 90% duplicates once)."""
    values = _values(memories)
    dupes = {v for v in values if values.count(v) > 1 and v}
    assert not dupes, f"exact duplicate memory values: {sorted(dupes)[:10]}"


def test_no_alice_in_store(memories: list[dict]) -> None:
    """Regression: a unit test used to write 'Alice' into the real store."""
    offenders = [m for m in memories if "alice" in _norm(m.get("value"))]
    assert not offenders, f"bogus 'Alice' memory resurfaced: {offenders}"