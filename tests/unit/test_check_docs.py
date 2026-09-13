"""Unit tests for scripts/check_docs.py — the documentation hygiene checker.

The checker enforces three mechanical rules from docs/DOC-GOVERNANCE.md. Each test
below pins one rule *and* the reason the rule exists, so a future "fix" that
weakens a rule fails here rather than silently letting stale docs back in.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_docs.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_docs", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_docs"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cd():
    return _load()


# ── Rule 2: status header ────────────────────────────────────────────────────


def test_missing_status_header_is_reported(cd):
    findings = cd.check_status(Path("docs/X.md"), "# Title\n\nJust prose, no header.\n")
    assert findings and "missing" in findings[0]


def test_valid_status_header_passes(cd):
    for status in ("ACTIVE", "SNAPSHOT", "HISTORICAL", "DRAFT"):
        text = f"# T\n\n**Status**: {status}\n**Last Updated**: 2026-09-13\n"
        assert cd.check_status(Path("docs/X.md"), text) == []


def test_unknown_status_value_is_rejected(cd):
    """A doc must not invent its own status vocabulary — that is how 'IMPLEMENTED
    (forensic-verified)' read like an authority while describing stale state."""
    text = "# T\n\n**Status**: IMPLEMENTED (forensic-verified)\n"
    findings = cd.check_status(Path("docs/X.md"), text)
    assert findings and "not one of" in findings[0]


def test_status_is_matched_case_insensitively(cd):
    assert cd.check_status(Path("docs/X.md"), "# T\n\n**Status**: active\n") == []


# ── Rule 3: no stub tables ───────────────────────────────────────────────────


def test_empty_table_is_reported(cd):
    text = "# T\n\n| Symbol | Type |\n| :--- | :--- |\n\nDone.\n"
    findings = cd.check_stub_tables(Path("docs/X.md"), text)
    assert findings and "empty table" in findings[0]


def test_table_with_rows_passes(cd):
    text = "# T\n\n| Symbol | Type |\n| :--- | :--- |\n| `foo` | function |\n"
    assert cd.check_stub_tables(Path("docs/X.md"), text) == []


def test_prose_pipes_are_not_tables(cd):
    assert cd.check_stub_tables(Path("docs/X.md"), "# T\n\nNot | a table\n") == []


# ── Rule 4: referenced paths resolve ─────────────────────────────────────────


def test_missing_qualified_path_is_reported(cd):
    text = "# T\n\nSee `docs/THIS_DOES_NOT_EXIST.md`.\n"
    findings = cd.check_paths(Path("docs/X.md"), text)
    assert findings and "does not exist" in findings[0]


def test_bare_basename_is_not_a_path_claim(cd):
    """``store.py`` in prose names a file loosely; resolving it would require
    guessing the directory, so it must not produce findings."""
    text = "# T\n\n`store.py` holds the JSON CRUD.\n"
    assert cd.check_paths(Path("docs/X.md"), text) == []


def test_existing_qualified_path_passes(cd):
    assert cd.check_paths(Path("docs/X.md"), "# T\n\n`app/memory/store.py`\n") == []


def test_sibling_doc_reference_resolves_from_docs_dir(cd):
    """Documents inside docs/ legitimately cite siblings by bare name."""
    assert cd.check_paths(Path("docs/X.md"), "# T\n\n`ARCHITECTURE.md`\n") == []


def test_urls_globs_and_absolutes_are_skipped(cd):
    text = (
        "# T\n\n"
        "`https://example.com/a.py` `~/x/y.py` `/etc/hosts.md` "
        "`docs/**.md` `docs/{a,b}.md`\n"
    )
    assert cd.check_paths(Path("docs/X.md"), text) == []


def test_runtime_data_paths_are_accepted(cd):
    """data/ and artifacts/ are produced at runtime and never committed, so a doc
    citing them is correct even though nothing is on disk."""
    text = "# T\n\n`data/memories.json` `artifacts/sbom-abc.cdx.json`\n"
    assert cd.check_paths(Path("docs/X.md"), text) == []


def test_historical_docs_are_exempt_from_path_checks(cd):
    """docs/archive/ and the symbol registry exist precisely to record code that
    was deleted; checking their paths would defeat their purpose."""
    text = "# T\n\n`app/knowledge/rag.py`\n"
    assert cd.check_paths(Path("docs/archive/CHANGELOG_v3.0.0.md"), text) == []
    assert cd.check_paths(Path("docs/SYMBOL_LINEAGE.md"), text) == []


# ── Rule 1: one navigation map ───────────────────────────────────────────────


def test_second_navigation_map_is_rejected(cd):
    findings = cd.check_single_map(Path("docs/INDEX.md"), "# JARVIS Documentation Index\n")
    assert findings and "only map" in findings[0]


def test_docs_readme_is_allowed_to_be_the_map(cd):
    assert cd.check_single_map(Path("docs/README.md"), "# JARVIS Documentation Guide\n") == []


def test_ordinary_title_is_not_a_map(cd):
    assert cd.check_single_map(Path("docs/ROADMAP.md"), "# JARVIS Roadmap\n") == []


# ── end-to-end: the real repo must be clean ──────────────────────────────────


def test_real_repository_is_clean(cd):
    """The whole point: HEAD's documentation must satisfy every rule."""
    findings = []
    for rel in cd.iter_docs():
        text = (cd.REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        findings += cd.check_status(rel, text)
        findings += cd.check_stub_tables(rel, text)
        findings += cd.check_paths(rel, text)
        findings += cd.check_single_map(rel, text)
    assert findings == [], "documentation findings:\n" + "\n".join(findings)


def test_every_doc_has_a_status_header(cd):
    """Regression guard for the 2026-09-13 pass: before it, 61 of 69 docs had no
    status header, so a reader could not tell stale from current."""
    missing = []
    for rel in cd.iter_docs():
        text = (cd.REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        if cd.check_status(rel, text):
            missing.append(str(rel))
    assert missing == [], f"docs without a valid status header: {missing}"


def test_only_one_navigation_map_exists(cd):
    maps = []
    for rel in cd.iter_docs():
        text = (cd.REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        if cd.check_single_map(rel, text):
            maps.append(str(rel))
    assert maps == [], f"duplicate navigation maps: {maps}"
