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


# ── Rule 5: no version pinned in an active doc's title ───────────────────────


def test_active_doc_pinning_version_in_title_is_reported(cd):
    """A doc edited across releases must not carry a frozen version label. This
    is how ARCHITECTURE.md read as a v3.0.0 artefact while describing v3.3.x."""
    text = "# JARVIS Architecture — Living Document v3.0.0\n\n**Status**: ACTIVE\n"
    findings = cd.check_stale_version_banner(Path("docs/ARCHITECTURE.md"), text)
    assert findings and "rule 5" in findings[0]


def test_active_doc_title_with_backticked_version_is_reported(cd):
    text = "# Data Flow Architecture (`v3.0.0 Refactored`)\n\n**Status**: ACTIVE\n"
    assert cd.check_stale_version_banner(Path("docs/architecture/data_flow.md"), text)


def test_clean_title_passes(cd):
    text = "# JARVIS Architecture\n\n**Status**: ACTIVE\n"
    assert cd.check_stale_version_banner(Path("docs/ARCHITECTURE.md"), text) == []


def test_version_in_body_is_allowed(cd):
    """Citing a release in the body is legitimate; only the title is a claim."""
    text = "# JARVIS Roadmap\n\n**Status**: ACTIVE\n\nShipped in v3.2.2 and v3.3.0.\n"
    assert cd.check_stale_version_banner(Path("docs/ROADMAP.md"), text) == []


def test_historical_doc_may_pin_a_version(cd):
    text = "# Health Report v3.0.0\n\n**Status**: HISTORICAL\n"
    assert (
        cd.check_stale_version_banner(Path("docs/archive/HEALTH_REPORT_2026-07-28.md"), text) == []
    )


def test_archived_doc_is_exempt_even_when_mislabelled(cd):
    text = "# Old Thing v2.1.0\n\n**Status**: ACTIVE\n"
    assert cd.check_stale_version_banner(Path("docs/archive/OLD_v2.1.0.md"), text) == []


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
        findings += cd.check_stale_version_banner(rel, text)
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


# ── Rule 10: the doc-type contract (docs/DOC-GOVERNANCE.md §10) ──────────────
#
# These pin the *anti-drift* mechanism, not merely the syntax. A test that only
# checked "is the word Type present" would pass while the contract did nothing.


def test_missing_type_is_reported(cd):
    findings = cd.check_types(Path("docs/X.md"), "# Title\n\n**Status**: ACTIVE\n\nBody.\n")
    assert findings and "missing '**Type**" in findings[0]


def test_unknown_type_is_reported(cd):
    text = "# T\n\n**Status**: ACTIVE\n**Type**: blogpost\n"
    findings = cd.check_types(Path("docs/X.md"), text)
    assert findings and "not one of" in findings[0]


def test_reference_without_source_is_reported(cd):
    """The Source binding is the load-bearing rule: without it, moving the code
    cannot break the document, so the document cannot be caught going stale."""
    text = "# T\n\n**Status**: ACTIVE\n**Type**: reference\n**Last Updated**: 2026-09-13\n"
    findings = cd.check_types(Path("docs/X.md"), text)
    assert any("requires '**Source**'" in f for f in findings), findings


def test_reference_with_source_passes(cd):
    text = (
        "# T\n\n**Status**: ACTIVE\n**Type**: reference\n"
        "**Last Updated**: 2026-09-13\n**Source**: `app/config/` at HEAD\n"
    )
    assert cd.check_types(Path("docs/X.md"), text) == []


def test_architecture_without_overview_section_is_reported(cd):
    text = (
        "# T\n\n**Status**: ACTIVE\n**Type**: architecture\n"
        "**Last Updated**: 2026-09-13\n**Source**: `app/` at HEAD\n\n## Details\n\nx\n"
    )
    findings = cd.check_types(Path("docs/X.md"), text)
    assert any("requires a section matching" in f for f in findings), findings


def test_register_without_table_is_reported(cd):
    """A register with no rows is a stub, which is how these documents died
    the first time."""
    text = (
        "# T\n\n**Status**: ACTIVE\n**Type**: register\n**Last Updated**: 2026-09-13\n\n## R\n\nx\n"
    )
    findings = cd.check_types(Path("docs/X.md"), text)
    assert any("populated table" in f for f in findings), findings


def test_generated_doc_must_name_its_generator(cd):
    text = "# T\n\n**Status**: SNAPSHOT\n**Type**: generated\n**Last Updated**: 2026-09-13\n"
    findings = cd.check_types(Path("docs/X.md"), text)
    assert any("Generated by" in f for f in findings), findings


def test_frozen_doc_needs_no_sections(cd):
    """Requiring maintained structure from a record of the past would be
    incoherent — and would tempt authors to edit history to satisfy a checker."""
    text = "# T\n\n**Status**: HISTORICAL\n**Type**: reference\n"
    assert cd.check_types(Path("docs/archive/X.md"), text) == []


def test_adr_outside_adr_dir_is_reported(cd):
    text = (
        "# T\n\n**Status**: ACTIVE\n**Type**: adr\n"
        "**Last Updated**: 2026-09-13\n\n## Decision\n## Consequences\n"
    )
    findings = cd.check_types(Path("docs/decisions/X.md"), text)
    assert any("must live at docs/adr/" in f for f in findings), findings


def test_recent_adr_must_record_alternatives(cd):
    """An ADR that rejects nothing teaches nothing: the options considered are
    unrecoverable once the decision is made."""
    text = (
        "# ADR-099: X\n\n**Status**: ACTIVE\n**Type**: adr\n**Last Updated**: 2026-09-20\n"
        "- **Date**: 2026-09-20\n\n## Decision\n\nWe did X.\n\n## Consequences\n\nFine.\n"
    )
    findings = cd.check_types(Path("docs/adr/ADR-099-x.md"), text)
    assert any("Alternatives considered" in f for f in findings), findings


def test_adr_before_cutover_is_not_required_to_have_alternatives(cd):
    """The rule is prospective. Retrofitting it onto ADR-001 would mean inventing
    rejected options nobody recorded."""
    text = (
        "# ADR-099: X\n\n**Status**: HISTORICAL\n**Type**: adr\n**Last Updated**: 2026-06-01\n"
        "- **Date**: 2026-06-01\n\n## Decision\n\nX.\n\n## Consequences\n\nY.\n"
    )
    assert cd.check_types(Path("docs/adr/ADR-099-x.md"), text) == []


# ── Whole-repository invariants ──────────────────────────────────────────────


def test_every_doc_declares_a_valid_type(cd):
    bad = []
    for rel in cd.iter_docs():
        text = (cd.REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        findings = cd.check_types(rel, text)
        if findings:
            bad.append(f"{rel}: {findings[0]}")
    assert bad == [], f"documents violating the type contract: {bad}"


def test_documented_type_table_matches_the_code(cd):
    """docs/DOC-GOVERNANCE.md §10 is generated. If it drifts from
    scripts/doc_types.py, the contract documents rules nothing enforces."""
    import subprocess

    res = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "doc_type_table.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert res.returncode == 0, res.stdout + res.stderr


def test_type_contract_covers_every_documented_type(cd):
    """Guard against a type being added to the prose but not the code (or the
    reverse): the governance doc must document exactly the types that exist."""
    from doc_types import TYPES

    gov = (REPO_ROOT / "docs" / "DOC-GOVERNANCE.md").read_text(encoding="utf-8")
    for name in TYPES:
        assert f"`{name}`" in gov, f"type '{name}' is not documented in §10"


# ── The gate covers NEW work, not just changed work ──────────────────────────
#
# These three tests exist because the gate's coverage of new documents was an
# assumption, not a measured fact. check_docs walks the tree with rglob, so it
# should catch a document the moment it exists — but "should" is what let the
# pre-commit hook be documented as running the checker for months while it did
# not. Each test plants a real file in the real repository and asserts the real
# command notices, then removes it.


def _run_check_docs() -> tuple[int, str]:
    import subprocess

    res = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_docs.py"), "--strict"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return res.returncode, res.stdout + res.stderr


def test_new_document_without_a_type_fails_the_gate():
    """A NEW file missing `**Type**` must fail, not just a modified one."""
    planted = REPO_ROOT / "docs" / "ZZ-TEST-GATE-NEW-DOC.md"
    planted.write_text("# Planted\n\n**Status**: ACTIVE\n\nNo type declared.\n")
    try:
        code, out = _run_check_docs()
    finally:
        planted.unlink(missing_ok=True)
    assert code != 0, "the gate accepted a brand-new document with no type"
    assert "ZZ-TEST-GATE-NEW-DOC.md" in out
    assert "Type" in out


def test_new_document_unreachable_from_the_index_fails_the_gate():
    """A new doc that is valid but that nothing links to must still fail.

    docs/README.md is the only map, so an unlinked document is one no reader can
    find. This is the rule that catches "the agent wrote a doc and told nobody".
    """
    planted = REPO_ROOT / "docs" / "ZZ-TEST-GATE-ORPHAN-DOC.md"
    planted.write_text(
        "# Planted Orphan\n\n"
        "**Status**: ACTIVE\n"
        "**Type**: guide\n"
        "**Last Updated**: 2026-09-30\n\n"
        "Nothing links here.\n"
    )
    try:
        code, out = _run_check_docs()
    finally:
        planted.unlink(missing_ok=True)
    assert code != 0, "the gate accepted an orphan document"
    assert "ZZ-TEST-GATE-ORPHAN-DOC.md" in out
    assert "not reachable from the index" in out


def test_the_pre_commit_hook_runs_the_documentation_gate():
    """Pin the wiring itself, because the wiring is what was missing.

    docs/DOC-GOVERNANCE.md §10.1 step 5 claims this hook enforces the checker.
    Before 2026-09-30 it did not — the hook ran the fact sync and the type-table
    sync but never check_docs, so a document violating its type contract could
    be committed and was only rejected at push. A claim in a governance document
    is not enforcement; this test is.
    """
    hook = (REPO_ROOT / "githooks" / "pre-commit").read_text(encoding="utf-8")
    assert "check_docs.py" in hook, (
        "githooks/pre-commit no longer runs check_docs.py, so "
        "docs/DOC-GOVERNANCE.md §10.1 step 5 is false again"
    )
    # Not merely mentioned: the INVOCATION must exist, and it must be able to
    # stop the commit. Matching the raw text is not enough -- the first mention
    # of "check_docs.py" in the hook is inside the explanatory comment, so a
    # substring search passes even if the command line is deleted.
    lines = hook.splitlines()
    invocations = [
        i for i, ln in enumerate(lines) if "check_docs.py" in ln and not ln.lstrip().startswith("#")
    ]
    assert invocations, "check_docs.py appears only in comments; the hook does not actually run it"
    for i in invocations:
        following = "\n".join(lines[i : i + 8])
        if "--strict" in lines[i] or "--strict" in following:
            assert "exit 1" in following, (
                "the hook runs check_docs.py but does not refuse the commit when "
                "it fails, so the gate reports without enforcing"
            )
            break
    else:
        raise AssertionError("check_docs.py is invoked without --strict")
