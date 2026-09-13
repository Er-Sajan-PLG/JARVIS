"""Unit tests for scripts/doc_review_due.py — the staleness review clock.

The clock decides *which* documents need a semantic re-read. Its failure mode is
silent: if it reports "nothing due" when things are stale, governance quietly
stops happening. These tests pin both directions, and — critically — that the
clock is driven by **explicit review evidence only**, never by git activity.

The prior version of this module used `max(touched, explicit)` as the basis,
meaning any commit (including an automated fact-sync commit) silenced a stale
document. These tests now pin the corrected semantics: only `**Reviewed**`
advances the clock; commits are advisory context only.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "doc_review_due", REPO_ROOT / "scripts" / "doc_review_due.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["doc_review_due"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def drd():
    return _load()


# ── explicit Reviewed marker ─────────────────────────────────────────────────


def test_reviewed_marker_is_parsed(drd):
    text = "# T\n\n**Status**: ACTIVE\n**Reviewed**: 2026-09-13\n"
    assert drd.reviewed_in_text(text) == date(2026, 9, 13)


def test_missing_reviewed_marker_is_none(drd):
    assert drd.reviewed_in_text("# T\n\n**Status**: ACTIVE\n") is None


def test_reviewed_marker_inside_code_is_still_parsed(drd):
    """The line carries the date; decoration around it should not hide it."""
    text = "# T\n\n**Reviewed**: `2026-01-02`\n"
    assert drd.reviewed_in_text(text) == date(2026, 1, 2)


def test_garbage_date_degrades_to_none(drd):
    assert drd.reviewed_in_text("# T\n\n**Reviewed**: soon\n") is None


def test_future_date_is_rejected(drd):
    """A review date in the future cannot be evidence of a review that happened;
    accepting it would let a typo (2026-12-13 for 2026-09-13) park a document
    permanently out of the review queue."""
    from datetime import timedelta

    future = date.today() + timedelta(days=10)
    text = f"# T\n\n**Status**: ACTIVE\n**Reviewed**: {future.isoformat()}\n"
    assert drd.reviewed_in_text(text) is None


# ── the due calculation ──────────────────────────────────────────────────────


def _mkdoc(tmp_path: Path, status: str = "ACTIVE", extra: str = "") -> Path:
    d = tmp_path / "docs"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "X.md"
    p.write_text(f"# X\n\n**Status**: {status}\n{extra}")
    return p


def test_never_reviewed_doc_is_due(drd, monkeypatch, tmp_path):
    """No review marker means no evidence of review — must not read as 'fresh',
    even if the file was just committed."""
    doc = _mkdoc(tmp_path)
    monkeypatch.setattr(drd, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(drd, "iter_docs", lambda: [doc])
    monkeypatch.setattr(drd, "last_touched", lambda rel: date(2026, 9, 1))
    monkeypatch.setattr(drd, "CADENCE_DAYS", {"docs/X.md": 90})
    rows = drd.assess(today=date(2026, 9, 13))
    assert rows[0]["due"] is True
    assert rows[0]["last_reviewed"] is None
    # No review marker -> no "edits since review" window exists to count; the
    # absence of evidence is the signal itself.
    assert rows[0]["edits_since_review"] is None


def test_explicit_review_within_cadence_is_not_due(drd, monkeypatch, tmp_path):
    """An explicit `**Reviewed**` within the cadence window silences the clock."""
    d = tmp_path / "docs"
    d.mkdir(parents=True)
    (d / "X.md").write_text("# X\n\n**Status**: ACTIVE\n**Reviewed**: 2026-09-12\n")
    monkeypatch.setattr(drd, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(drd, "iter_docs", lambda: [d / "X.md"])
    monkeypatch.setattr(drd, "CADENCE_DAYS", {"docs/X.md": 90})
    rows = drd.assess(today=date(2026, 9, 13))
    assert rows[0]["due"] is False
    assert rows[0]["last_reviewed"] == "2026-09-12"


def test_explicit_review_past_cadence_is_due(drd, monkeypatch, tmp_path):
    """A review older than the cadence does not protect the document."""
    d = tmp_path / "docs"
    d.mkdir(parents=True)
    (d / "X.md").write_text("# X\n\n**Status**: ACTIVE\n**Reviewed**: 2026-01-01\n")
    monkeypatch.setattr(drd, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(drd, "iter_docs", lambda: [d / "X.md"])
    monkeypatch.setattr(drd, "last_touched", lambda rel: date(2026, 9, 1))
    monkeypatch.setattr(drd, "CADENCE_DAYS", {"docs/X.md": 90})
    rows = drd.assess(today=date(2026, 9, 13))
    assert rows[0]["due"] is True
    assert rows[0]["last_reviewed"] == "2026-01-01"


def test_commit_after_review_preserves_clock(drd, monkeypatch, tmp_path):
    """REGRESSION for the core D1 defect.

    A fact-sync commit (or any mechanical edit) that touches the file *after* a
    valid review must NOT reset the clock. Only the explicit marker advances it.
    """
    d = tmp_path / "docs"
    d.mkdir(parents=True)
    (d / "X.md").write_text("# X\n\n**Status**: ACTIVE\n**Reviewed**: 2026-01-01\n")
    monkeypatch.setattr(drd, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(drd, "iter_docs", lambda: [d / "X.md"])
    monkeypatch.setattr(drd, "last_touched", lambda rel: date(2026, 9, 10))
    monkeypatch.setattr(drd, "CADENCE_DAYS", {"docs/X.md": 90})
    rows = drd.assess(today=date(2026, 9, 13))
    # Review is 255 days old > 90-day cadence -> still due, despite a recent commit.
    assert rows[0]["due"] is True
    assert rows[0]["last_reviewed"] == "2026-01-01"


def test_snapshot_and_historical_docs_are_skipped(drd, monkeypatch, tmp_path):
    """Dated and historical docs are frozen by definition; a cadence on them is
    meaningless and would generate permanent noise."""
    d = tmp_path / "docs"
    d.mkdir(parents=True)
    (d / "A.md").write_text("# A\n\n**Status**: HISTORICAL\n")
    (d / "B.md").write_text("# B\n\n**Status**: SNAPSHOT\n")
    (d / "C.md").write_text("# C\n\n**Status**: ACTIVE\n")
    monkeypatch.setattr(drd, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(drd, "iter_docs", lambda: sorted(d.glob("*.md")))
    monkeypatch.setattr(drd, "last_touched", lambda rel: None)
    got = {r["doc"] for r in drd.assess(today=date(2026, 9, 13))}
    assert got == {"docs/C.md"}


def test_archive_and_adr_are_exempt(drd):
    """Decisions and archived material are immutable — never on a cadence."""
    for rel in (
        "docs/archive/OLD.md",
        "docs/adr/ADR-001-x.md",
        "docs/timelines/x.md",
    ):
        assert rel.startswith(drd.EXEMPT_PREFIXES)


# ── context: git is advisory, not authoritative ───────────────────────────────


def test_reviews_surfaced_with_git_context(drd, monkeypatch, tmp_path):
    """Commits surrounding a review are reported as advisory context on the row,
    so a reviewer can see 'this was committed 50 times since review' without the
    clock being fooled by those commits."""
    d = tmp_path / "docs"
    d.mkdir(parents=True)
    (d / "X.md").write_text("# X\n\n**Status**: ACTIVE\n**Reviewed**: 2026-01-01\n")
    monkeypatch.setattr(drd, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(drd, "iter_docs", lambda: [d / "X.md"])
    monkeypatch.setattr(drd, "commits_since", lambda iso: 42)  # noqa
    monkeypatch.setattr(drd, "CADENCE_DAYS", {"docs/X.md": 90})
    rows = drd.assess(today=date(2026, 9, 13))
    assert rows[0]["edits_since_review"] == 42


# ── the packet ───────────────────────────────────────────────────────────────


def test_packet_names_every_due_document(drd):
    rows = [
        {
            "doc": "docs/A.md",
            "cadence_days": 90,
            "last_reviewed": "2026-01-01",
            "age_days": 255,
            "due": True,
            "overdue_by": 165,
            "edits_since_review": None,
        },
        {
            "doc": "docs/B.md",
            "cadence_days": 90,
            "last_reviewed": "2026-09-12",
            "age_days": 1,
            "due": False,
            "overdue_by": -89,
        },
    ]
    out = drd.packet(rows)
    assert "docs/A.md" in out
    assert "docs/B.md" not in out
    assert "Still true?" in out


def test_packet_describes_review_as_clock_reset(drd, monkeypatch, tmp_path):
    """D7: the packet must explain that `**Reviewed**` — not `**Last Updated**` —
    resets the review clock. The old text said 'set Last Updated' while the actual
    clock basis was the last-commit date; that disconnect let mechanical edits
    masquerade as review evidence."""
    rows = [
        {
            "doc": "docs/A.md",
            "cadence_days": 90,
            "last_reviewed": None,
            "age_days": 1,
            "due": True,
            "overdue_by": 90,
            "edits_since_review": None,
        }
    ]
    out = drd.packet(rows)
    assert "**Reviewed**" in out
    # The packet must name **Reviewed** as the clock-resetting field.
    assert "resets the review clock" in out


# ── end-to-end against the real repo ─────────────────────────────────────────


def test_real_repo_assessment_is_well_formed(drd):
    """Every living doc gets an assessment with a sane cadence and status."""
    rows = drd.assess()
    assert rows, "no living documents were assessed"
    for r in rows:
        assert isinstance(r["cadence_days"], int) and r["cadence_days"] > 0
        assert r["due"] in (True, False)
        assert str(r["doc"]).startswith("docs/")
