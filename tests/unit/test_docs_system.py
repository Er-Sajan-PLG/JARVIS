"""Tests for the autonomous documentation system (Layer 1+2 + manifest)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_SCRIPTS = REPO_ROOT / "scripts" / "docs"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_manifest = _load("test_docs_manifest", DOCS_SCRIPTS / "manifest-validate.py")
_generate = _load("test_docs_generate", DOCS_SCRIPTS / "generate.py")
_check_full = _load("test_docs_check_full", DOCS_SCRIPTS / "check-full.py")
_sync = _load("test_docs_sync", REPO_ROOT / "scripts" / "sync_doc_facts.py")


def test_manifest_covers_whole_tree() -> None:
    assert _manifest.validate() == []


def test_manifest_expected_docs_nonempty() -> None:
    docs = _manifest.expected_docs()
    assert len(docs) > 100
    assert "docs/TOOLS.md" in docs
    assert "app/modes/README.md" in docs


def test_generate_is_deterministic_and_clean() -> None:
    assert _generate.targets() == _generate.targets()
    assert _generate.check_all() == []


def test_snippet_checker_catches_syntax_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text("# T\n\n```python\ndef broken(:\n```\n", encoding="utf-8")
    errors: list[str] = []
    _check_full.check_snippets(bad, errors)
    assert len(errors) == 1
    assert "bad.md" in errors[0]

    good = tmp_path / "good.md"
    good.write_text("# T\n\n```python\nawait fetch(url)\n```\n", encoding="utf-8")
    errors.clear()
    _check_full.check_snippets(good, errors)
    assert errors == []


def test_reconcile_rejects_stale_snapshot() -> None:
    """A cache from another commit must not survive as writable facts.

    test_count is ALWAYS recomputed live (never trusted from a snapshot);
    coverage survives only on commit match.
    """
    reconciled = _sync.reconcile_injected_facts(
        {"commit": "deadbeef", "test_count": "1", "coverage": "1", "gate_count": "1"}
    )

    assert reconciled["test_count"] != "1"
    assert reconciled["test_count"].isdigit()
    assert reconciled["coverage"] == "unknown"
    # Cheap facts are always recomputed live, even from a stale snapshot.
    assert reconciled["gate_count"] != "1"


def test_reconcile_accepts_current_snapshot() -> None:
    import subprocess

    head = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    reconciled = _sync.reconcile_injected_facts(
        {"commit": head, "test_count": "1746", "coverage": "88"}
    )

    # test_count comes from live --collect-only, never from the snapshot.
    assert reconciled["test_count"].isdigit()
    assert reconciled["coverage"] == "88"


def test_f7_catches_stale_marker() -> None:
    live = {"test_count": "1746", "gate_count": "28"}
    findings = _check_full.check_fact_markers(
        "a <!--fact:test_count-->1000<!--/fact--> b <!--fact:gate_count-->28<!--/fact--> c",
        live,
    )

    assert len(findings) == 1
    assert "'1000'" in findings[0] and "'1746'" in findings[0]
    assert _check_full.check_fact_markers("<!--fact:test_count-->1746<!--/fact-->", live) == []


def test_layer1_ignores_unstaged_worktree_noise() -> None:
    """Stash-safety: Layer 1 reads the staged snapshot + HEAD only.

    Regression test for the verification-time stash-cycle incident: unstaged
    worktree content (what pre-commit stashes away mid-run) must not change
    Layer 1 output. Uses the real repo but stages nothing and restores the
    one touched file, so the tree is untouched afterward.
    """
    import subprocess

    _changed = _load("test_docs_check_changed", DOCS_SCRIPTS / "check-changed.py")
    voice = REPO_ROOT / "docs" / "VOICE.md"
    original = voice.read_text(encoding="utf-8")
    before = _changed.check([])
    try:
        with voice.open("a", encoding="utf-8") as handle:
            handle.write("\nUnstaged probe line that must not affect Layer 1.\n")
        during = _changed.check([])
    finally:
        voice.write_text(original, encoding="utf-8")
    assert before == during
    assert voice.read_text(encoding="utf-8") == original
    # And the tree really is untouched (nothing staged by the check itself).
    staged = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    assert "docs/VOICE.md" not in staged.splitlines()


def test_spelling_checker_flags_typo(tmp_path: Path) -> None:
    doc = tmp_path / "typo.md"
    doc.write_text("# T\n\nTeh quick brown fox.\n", encoding="utf-8")
    errors: list[str] = []
    _check_full.check_spelling(doc, errors)
    assert len(errors) == 1
    assert "Teh" in errors[0]
