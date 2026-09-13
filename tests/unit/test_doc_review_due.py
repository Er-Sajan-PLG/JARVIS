"""Unit tests for scripts/doc_review_due.py — the staleness review clock.

The clock decides *which* documents need a semantic re-read. Its failure mode is
silent: if it reports "nothing due" when things are stale, governance quietly
stops happening. These tests pin both directions.
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


# ── the due calculation ──────────────────────────────────────────────────────


def _mkdoc(tmp_path: Path, status: str = "ACTIVE", extra: str = "") -> Path:
    d = tmp_path / "docs"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "X.md"
    p.write_text(f"# X\n\n**Status**: {status}\n{extra}")
    return p


def test_doc_newer_than_cadence_is_not_due(drd, monkeypatch, tmp_path):
    doc = _mkdoc(tmp_path)
    monkeypatch.setattr(drd, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(drd, "iter_docs", lambda: [doc])
    monkeypatch.setattr(drd, "last_touched", lambda rel: date(2026, 9, 1))
    monkeypatch.setattr(drd, "CADENCE_DAYS", {"docs/X.md": 90})
    rows = drd.assess(today=date(2026, 9, 13))
    assert rows and rows[0]["due"] is False


def test_doc_past_cadence_is_due_and_reports_overdue_by(drd, monkeypatch, tmp_path):
    doc = _mkdoc(tmp_path)
    monkeypatch.setattr(drd, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(drd, "iter_docs", lambda: [doc])
    monkeypatch.setattr(drd, "last_touched", lambda rel: date(2026, 1, 1))
    monkeypatch.setattr(drd, "CADENCE_DAYS", {"docs/X.md": 90})
    rows = drd.assess(today=date(2026, 9, 13))
    assert rows[0]["due"] is True
    assert rows[0]["overdue_by"] == (255 - 90)


def test_never_reviewed_doc_is_due(drd, monkeypatch, tmp_path):
    """No git history means no evidence of review — must not read as 'fresh'."""
    doc = _mkdoc(tmp_path)
    monkeypatch.setattr(drd, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(drd, "iter_docs", lambda: [doc])
    monkeypatch.setattr(drd, "last_touched", lambda rel: None)
    rows = drd.assess(today=date(2026, 9, 13))
    assert rows[0]["due"] is True and rows[0]["last_reviewed"] is None


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
    for rel in ("docs/archive/OLD.md", "docs/adr/ADR-001-x.md", "docs/timelines/x.md"):
        assert rel.startswith(drd.EXEMPT_PREFIXES)


def test_reviewed_marker_wins_over_commit_age(drd, monkeypatch, tmp_path):
    """A deliberate `**Reviewed**:` acknowledgement is stronger evidence than the
    last commit date, which may just be a typo fix."""
    d = tmp_path / "docs"
    d.mkdir(parents=True)
    (d / "X.md").write_text("# X\n\n**Status**: ACTIVE\n**Reviewed**: 2026-09-12\n")
    monkeypatch.setattr(drd, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(drd, "iter_docs", lambda: [d / "X.md"])
    monkeypatch.setattr(drd, "last_touched", lambda rel: date(2020, 1, 1))
    monkeypatch.setattr(drd, "CADENCE_DAYS", {"docs/X.md": 90})
    rows = drd.assess(today=date(2026, 9, 13))
    assert rows[0]["due"] is False
    assert rows[0]["last_reviewed"] == "2026-09-12"


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


# ── end-to-end against the real repo ─────────────────────────────────────────


def test_real_repo_assessment_is_well_formed(drd):
    """Every living doc gets an assessment with a sane cadence and status."""
    rows = drd.assess()
    assert rows, "no living documents were assessed"
    for r in rows:
        assert isinstance(r["cadence_days"], int) and r["cadence_days"] > 0
        assert r["due"] in (True, False)
        assert str(r["doc"]).startswith("docs/")
