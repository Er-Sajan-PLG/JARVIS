"""Unit tests for scripts/doc_links.py — link, anchor, heading and index checks.

These pin the checks that a path-only checker misses. The anchor case is the reason
the module exists: the file exists, the link looks right, and the heading it points
at was renamed two releases ago.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "doc_links.py"


def _load():
    spec = importlib.util.spec_from_file_location("doc_links", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["doc_links"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def dl():
    return _load()


# ── slug derivation ─────────────────────────────────────────────────────────


def test_slug_matches_github_conventions(dl):
    """The slug rules must match GitHub's, or every anchor is a false positive."""
    assert dl._slug("Cognitive Engine Loop (Direct Async)") == "cognitive-engine-loop-direct-async"
    assert dl._slug("1. Local Development Setup") == "1-local-development-setup"
    assert (
        dl._slug("`Memory` Dataclass (`app/memory/schema.py`)")
        == "memory-dataclass-appmemoryschemapy"
    )


def test_slug_strips_link_and_emphasis_markup(dl):
    # GitHub slugs the link *text* and drops the URL entirely.
    assert dl._slug("See [ADR-013](adr/x.md) here") == "see-adr-013-here"
    assert dl._slug("**Bold** and *italic*") == "bold-and-italic"


# ── anchors ─────────────────────────────────────────────────────────────────


def test_headings_and_anchors_skips_fenced_code(dl):
    """A `# heading` inside a fence is example text, not a real heading."""
    text = "# Real\n\n```\n# Not a heading\n```\n\n## Second\n"
    titles, anchors = dl.headings_and_anchors(text)
    assert len(titles) == 2
    assert "not-a-heading" not in anchors
    assert "second" in anchors


def test_same_file_dead_anchor_is_reported(dl, tmp_path):
    text = "# Title\n\nSee [below](#renamed-section).\n\n## Actual Section\n"
    findings = dl.check_links(Path("docs/X.md"), text, tmp_path, {})
    assert any("dead same-file anchor" in f for f in findings), findings


def test_same_file_live_anchor_passes(dl, tmp_path):
    text = "# Title\n\nSee [below](#actual-section).\n\n## Actual Section\n"
    assert dl.check_links(Path("docs/X.md"), text, tmp_path, {}) == []


def test_cross_file_dead_anchor_is_reported(dl, tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "OTHER.md").write_text("# Other\n\n## Some Section\n", encoding="utf-8")
    text = "# T\n\n[link](OTHER.md#missing-heading)\n"
    findings = dl.check_links(Path("docs/X.md"), text, tmp_path, {})
    assert any("dead anchor" in f and "missing-heading" in f for f in findings), findings


def test_cross_file_live_anchor_passes(dl, tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "OTHER.md").write_text("# Other\n\n## Some Section\n", encoding="utf-8")
    text = "# T\n\n[link](OTHER.md#some-section)\n"
    assert dl.check_links(Path("docs/X.md"), text, tmp_path, {}) == []


# ── links ───────────────────────────────────────────────────────────────────


def test_missing_link_target_is_reported(dl, tmp_path):
    findings = dl.check_links(Path("docs/X.md"), "# T\n\n[x](GONE.md)\n", tmp_path, {})
    assert any("does not exist" in f for f in findings), findings


def test_absolute_link_is_reported(dl, tmp_path):
    """An absolute path breaks for every reader but its author, and this repo has
    lived at more than one path."""
    findings = dl.check_links(
        Path("docs/X.md"), "# T\n\n[x](/home/someone/docs/A.md)\n", tmp_path, {}
    )
    assert any("absolute link" in f for f in findings), findings


def test_external_links_are_not_probed_here(dl, tmp_path):
    """Offline invariant: this module never touches the network."""
    text = "# T\n\n[x](https://example.com/whatever)\n"
    assert dl.check_links(Path("docs/X.md"), text, tmp_path, {}) == []


def test_link_inside_fence_is_not_a_link(dl, tmp_path):
    text = "# T\n\n```\n[x](GONE.md)\n```\n"
    assert dl.check_links(Path("docs/X.md"), text, tmp_path, {}) == []


# ── heading numbers ─────────────────────────────────────────────────────────


def test_duplicate_heading_number_is_reported(dl):
    text = "# T\n\n## 5. First\n\n### 5.1 Sub\n\n## 5. Second\n"
    findings = dl.check_heading_numbers(Path("docs/X.md"), text)
    assert any("already used" in f for f in findings), findings


def test_heading_number_inside_fence_is_ignored(dl):
    text = "# T\n\n```\n## 5. Example\n```\n\n## 5. Real\n"
    assert dl.check_heading_numbers(Path("docs/X.md"), text) == []


def test_distinct_heading_numbers_pass(dl):
    text = "# T\n\n## 1. A\n\n## 2. B\n\n### 2.1 C\n"
    assert dl.check_heading_numbers(Path("docs/X.md"), text) == []


# ── index coverage ──────────────────────────────────────────────────────────


def test_unreachable_document_is_reported(dl, tmp_path):
    (tmp_path / "docs" / "sub").mkdir(parents=True)
    (tmp_path / "docs" / "README.md").write_text("# Map\n", encoding="utf-8")
    (tmp_path / "docs" / "ORPHAN.md").write_text("# Orphan\n", encoding="utf-8")
    text = (tmp_path / "docs" / "README.md").read_text(encoding="utf-8")
    findings = dl.check_index_coverage(Path("docs/README.md"), text, tmp_path)
    assert any("not reachable" in f and "ORPHAN.md" in f for f in findings), findings


def test_directory_link_makes_contents_reachable(dl, tmp_path):
    """Linking a folder index row is how the real index works; demanding one row
    per file would turn the map into a second copy of the tree."""
    (tmp_path / "docs" / "sub").mkdir(parents=True)
    (tmp_path / "docs" / "sub" / "INNER.md").write_text("# Inner\n", encoding="utf-8")
    text = "# Map\n\n| [`sub/`](sub/) | inner docs |\n"
    assert dl.check_index_coverage(Path("docs/README.md"), text, tmp_path) == []


def test_archive_and_adr_are_not_index_checked(dl, tmp_path):
    (tmp_path / "docs" / "archive").mkdir(parents=True)
    (tmp_path / "docs" / "adr").mkdir()
    (tmp_path / "docs" / "archive" / "OLD.md").write_text("# Old\n", encoding="utf-8")
    (tmp_path / "docs" / "adr" / "ADR-001-x.md").write_text("# A\n", encoding="utf-8")
    assert dl.check_index_coverage(Path("docs/README.md"), "# Map\n", tmp_path) == []


def test_index_check_only_applies_to_the_index(dl, tmp_path):
    assert dl.check_index_coverage(Path("docs/OTHER.md"), "# X\n", tmp_path) == []


# ── whole-repository invariants ─────────────────────────────────────────────


def test_real_repository_links_are_clean(dl):
    findings = []
    cache: dict[str, set[str]] = {}
    for p in sorted(REPO_ROOT.glob("docs/**/*.md")) + [
        REPO_ROOT / n for n in ("README.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md")
    ]:
        if not p.is_file():
            continue
        rel = p.relative_to(REPO_ROOT)
        if str(rel) in {"docs/SYMBOL_LINEAGE.md"} or str(rel).startswith("docs/archive/"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        findings += dl.check_links(rel, text, REPO_ROOT, cache)
        findings += dl.check_heading_numbers(rel, text)
    assert findings == [], "link/heading findings:\n" + "\n".join(findings)
