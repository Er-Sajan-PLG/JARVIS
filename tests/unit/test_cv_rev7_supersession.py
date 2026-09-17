"""CV REV 7.0 must win on employers and dates; contact facts must coexist.

The owner supplied an earlier CV revision ("SAJAN GURUN CV REV 7.0.pdf") that
carried the real employment dates, and decided:

  * "Yes — this CV is the authority for dates and employers"
  * "Keep both emails"
  * Education: "Both are right — keep BOTH: Pokhara University (awarding) +
    Pokhara Engineering College (where I studied). The CV just simplifies it."

Before this, memory held LinkedIn-derived employers with wrong names
("RUCHI Real Estate Developers" vs the CV's "RUCHI DEVELOPER PVT. LTD."),
an open-ended "Aug 2025 to present", a "2 years 7 months" experience figure,
and two project records marked "[DATE TO CONFIRM]".
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


def _all(memories: list[dict]) -> str:
    return " || ".join(_norm(m.get("value")) for m in memories)


# ----- employers: CV REV 7.0 names win -----


def test_ruchi_developer_name_is_the_cv_name(memories: list[dict]) -> None:
    blob = _all(memories)
    assert "ruchi developer" in blob, "CV REV 7.0 employer name 'RUCHI DEVELOPER' is missing"


def test_no_stale_ruchi_real_estate_record(memories: list[dict]) -> None:
    """'RUCHI Real Estate Developers' was the LinkedIn wording, not the CV's."""
    offenders = [m.get("value") for m in memories if "ruchi real estate" in _norm(m.get("value"))]
    assert not offenders, f"stale RUCHI Real Estate records remain: {offenders}"


def test_roadshow_construction_name_is_the_cv_name(memories: list[dict]) -> None:
    blob = _all(memories)
    assert "roadshow construction" in blob, "CV REV 7.0 employer 'ROADSHOW CONSTRUCTION' is missing"


def test_no_stale_roadshow_real_estate_record(memories: list[dict]) -> None:
    offenders = [m.get("value") for m in memories if "roadshow real estate" in _norm(m.get("value"))]
    assert not offenders, f"stale Roadshow Real Estate records remain: {offenders}"


# ----- dates: closed ranges, not "present" -----


def test_ruchi_has_a_closed_date_range(memories: list[dict]) -> None:
    hits = [m for m in memories if m.get("type") == "work_period" and "ruchi" in _norm(m.get("value"))]
    assert hits, "no RUCHI work_period record"
    blob = " ".join(_norm(h.get("value")) for h in hits)
    assert "nov 2025" in blob or "11/2025" in blob or "2025-11" in blob, (
        f"RUCHI end date missing from CV: {blob}"
    )
    assert "to present" not in blob, f"RUCHI still open-ended: {blob}"


def test_roadshow_has_a_closed_date_range(memories: list[dict]) -> None:
    hits = [m for m in memories if m.get("type") == "work_period" and "roadshow" in _norm(m.get("value"))]
    assert hits, "no Roadshow work_period record"
    blob = " ".join(_norm(h.get("value")) for h in hits)
    assert "nov 2025" in blob or "11/2025" in blob or "2025-11" in blob, (
        f"Roadshow end date missing from CV: {blob}"
    )


def test_no_date_to_confirm_placeholder_survives(memories: list[dict]) -> None:
    """The CV supplied the dates, so the placeholder must be gone."""
    offenders = [m.get("value") for m in memories if "date to confirm" in _norm(m.get("value"))]
    assert not offenders, f"'[DATE TO CONFIRM]' still stored: {offenders}"


# ----- experience figure -----


def test_experience_no_longer_claims_two_years_seven_months(memories: list[dict]) -> None:
    """CV REV 7.0 states 1+ years; the LinkedIn 2y7m figure was superseded."""
    offenders = [
        m.get("value") for m in memories
        if m.get("type") == "experience" and "2 years 7 months" in _norm(m.get("value"))
    ]
    assert not offenders, f"superseded 2y7m experience claim remains: {offenders}"


# ----- education: BOTH, per owner's explicit choice -----


def test_both_university_and_college_are_kept(memories: list[dict]) -> None:
    """Owner: 'Both are right — keep BOTH'. The CV simplifies; memory must not."""
    blob = _all(memories)
    assert "pokhara university" in blob, "Pokhara University was dropped"
    assert "pokhara engineering college" in blob, "Pokhara Engineering College was dropped"


def test_degree_names_college_as_place_and_university_as_awarder(memories: list[dict]) -> None:
    degrees = [m for m in memories if m.get("type") == "degree"]
    assert degrees, "no degree record"
    v = _norm(degrees[0].get("value"))
    assert "pokhara engineering college" in v, f"degree omits the college: {v}"
    assert "pokhara university" in v, f"degree omits the university: {v}"


# ----- contact: both emails kept, per owner's choice -----


def test_both_emails_are_stored(memories: list[dict]) -> None:
    """Owner chose 'Keep both emails'."""
    emails = {_norm(m.get("value")) for m in memories if m.get("type") == "email"}
    assert "gurungsajan0228@gmail.com" in emails, f"older email missing: {emails}"
    assert "gurungsaajan588@gmail.com" in emails, f"CV REV 7.0 email missing: {emails}"


def test_cv_phone_is_stored(memories: list[dict]) -> None:
    blob = _all(memories)
    assert "9817199172" in blob, "CV REV 7.0 phone number missing"


def test_both_locations_recorded_without_contradiction(memories: list[dict]) -> None:
    """Pokhara (LinkedIn) and Lamjung (CV address) must both survive.

    Neither may be stored as a bare claim that erases the other.
    """
    locations = [_norm(m.get("value")) for m in memories if m.get("type") in ("location", "residence")]
    assert any("lamjung" in v for v in locations), f"CV Lamjung address missing: {locations}"
    assert any("pokhara" in v for v in locations), f"Pokhara location missing: {locations}"
    bare = [v for v in locations if v in ("pokhara, nepal", "pokhara")]
    assert not bare, f"ambiguous bare location record still present: {bare}"


# ----- languages and credentials from the CV -----


def test_languages_are_stored(memories: list[dict]) -> None:
    langs = {_norm(m.get("value")) for m in memories if m.get("type") == "language"}
    for expected in ("nepali", "english", "hindi", "japanese"):
        assert any(l.startswith(expected) for l in langs), f"language missing: {expected} in {langs}"


def test_nepal_engineering_association_membership_stored(memories: list[dict]) -> None:
    blob = _all(memories)
    assert "nepal engineering association" in blob, "professional membership missing"


def test_hilti_certification_stored(memories: list[dict]) -> None:
    blob = _all(memories)
    assert "hilti" in blob, "Hilti certification from CV REV 7.0 missing"


# ----- store hygiene -----


def test_no_exact_duplicate_values(memories: list[dict]) -> None:
    values = [_norm(m.get("value")) for m in memories]
    dupes = {v for v in values if values.count(v) > 1 and v}
    assert not dupes, f"exact duplicate memory values: {sorted(dupes)[:10]}"


def test_every_record_has_a_type(memories: list[dict]) -> None:
    """Untyped records cannot be filtered or corrected precisely."""
    untyped = [m.get("value") for m in memories if not m.get("type")]
    assert not untyped, f"records without a type: {untyped}"


def test_no_alice_in_store(memories: list[dict]) -> None:
    offenders = [m for m in memories if "alice" in _norm(m.get("value"))]
    assert not offenders, f"bogus 'Alice' memory resurfaced: {offenders}"