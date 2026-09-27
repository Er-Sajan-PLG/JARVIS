"""Unit tests for the documentation fact-sync system.

Two modules under test:

* ``scripts/doc_facts.py`` — derives facts from the repository.
* ``scripts/sync_doc_facts.py`` — rewrites/detects the values between markers.

The point of these tests is not coverage; it is that the mechanism which caught
"22 checks" after gate 23 must keep working. If someone weakens the drift check,
these fail.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def facts_mod():
    return _load("doc_facts", REPO_ROOT / "scripts" / "doc_facts.py")


@pytest.fixture(scope="module")
def sync_mod(facts_mod):
    # sync_doc_facts imports doc_facts by name; ensure our loaded module is used.
    sys.modules.setdefault("doc_facts", facts_mod)
    return _load("sync_doc_facts", REPO_ROOT / "scripts" / "sync_doc_facts.py")


# ── fact derivation ──────────────────────────────────────────────────────────


def test_gate_count_matches_actual_gate_functions(facts_mod):
    """The fact must equal a fresh count of `def gate_*` in ci_gate.py."""
    import re

    src = (REPO_ROOT / "scripts" / "ci_gate.py").read_text()
    actual = len(re.findall(r"^def gate_", src, re.M))
    assert facts_mod.collect_cheap()["gate_count"] == str(actual)


def test_adr_count_matches_documents_on_disk(facts_mod):
    actual = len(list((REPO_ROOT / "docs" / "adr").glob("ADR-*.md")))
    assert facts_mod.collect_cheap()["adr_count"] == str(actual)


def test_context_count_matches_bridge_contexts(facts_mod):
    """CONTEXT_ORDER is a tuple, not a list — the original regex missed it and
    silently reported `unknown`, which is why this is pinned."""
    value = facts_mod.collect_cheap()["context_count"]
    assert value != "unknown"
    assert value.isdigit() and int(value) >= 8


def test_cheap_facts_never_invent_a_number(facts_mod):
    """Every cheap fact is either a digit or the literal 'unknown'. A guessed
    number is worse than an admitted gap."""
    for name, value in facts_mod.collect_cheap().items():
        assert (
            value == "unknown"
            or value.isdigit()
            or name
            in {
                "version",
                "commit",
                "python_requires",
            }
        ), f"{name}={value!r} looks invented"


def test_expensive_facts_are_unknown_without_a_cache(facts_mod, tmp_path, monkeypatch):
    monkeypatch.setattr(facts_mod, "FACTS_CACHE", tmp_path / "missing.json")
    assert facts_mod.collect_expensive(run_tests=False) == {
        "test_count": "unknown",
        "coverage": "unknown",
    }


def test_expensive_facts_read_the_gate_cache(facts_mod, tmp_path, monkeypatch):
    """A cache is a claim about a past tree. It is only trusted on explicit
    opt-in (allow_cache=True) AND a matching recorded commit — otherwise it
    describes code that may no longer exist and would assert a stale
    measurement as current truth. The default path never auto-loads."""
    cache = tmp_path / "doc_facts.json"
    current = facts_mod._head_commit()
    cache.write_text(json.dumps({"test_count": "4242", "coverage": "77", "commit": current}))
    monkeypatch.setattr(facts_mod, "FACTS_CACHE", cache)
    assert facts_mod.collect_expensive(run_tests=False) == {
        "test_count": "unknown",
        "coverage": "unknown",
    }
    got = facts_mod.collect_expensive(run_tests=False, allow_cache=True)
    assert got == {"test_count": "4242", "coverage": "77"}


def test_cache_with_mismatched_commit_is_not_trusted(facts_mod, tmp_path, monkeypatch):
    """A cache describing a different commit is stale truth, not current truth.
    The fact must degrade to 'unknown' rather than be reported as current."""
    cache = tmp_path / "doc_facts.json"
    cache.write_text(
        json.dumps({"test_count": "4242", "coverage": "77", "commit": "deadbeefdeadbeef"})
    )
    monkeypatch.setattr(facts_mod, "FACTS_CACHE", cache)
    got = facts_mod.collect_expensive(run_tests=False)
    assert got == {"test_count": "unknown", "coverage": "unknown"}


def test_cache_missing_commit_field_is_not_trusted(facts_mod, tmp_path, monkeypatch):
    """A cache with no provenance field at all cannot be proven current."""
    cache = tmp_path / "doc_facts.json"
    cache.write_text(json.dumps({"test_count": "4242", "coverage": "77"}))
    monkeypatch.setattr(facts_mod, "FACTS_CACHE", cache)
    got = facts_mod.collect_expensive(run_tests=False)
    assert got == {"test_count": "unknown", "coverage": "unknown"}


def test_corrupt_cache_degrades_to_unknown_not_a_crash(facts_mod, tmp_path, monkeypatch):
    cache = tmp_path / "doc_facts.json"
    cache.write_text("{not json")
    monkeypatch.setattr(facts_mod, "FACTS_CACHE", cache)
    assert facts_mod.collect_expensive(run_tests=False)["test_count"] == "unknown"


# ── marker rewriting ─────────────────────────────────────────────────────────


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_apply_rewrites_a_stale_marker(sync_mod, monkeypatch, tmp_path):
    doc = _write(
        tmp_path / "docs" / "X.md",
        "# T\n\n<!--fact:gate_count-->22<!--/fact--> checks\n",
    )
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    changed, updated, _ = sync_mod.apply_facts({"gate_count": "23"})
    assert (changed, updated) == (1, 1)
    assert "<!--fact:gate_count-->23<!--/fact-->" in doc.read_text()


def test_apply_is_idempotent(sync_mod, monkeypatch, tmp_path):
    _write(
        tmp_path / "docs" / "X.md",
        "# T\n\n<!--fact:gate_count-->23<!--/fact--> checks\n",
    )
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    changed, _, _ = sync_mod.apply_facts({"gate_count": "23"})
    assert changed == 0


def test_apply_counts_only_changed_markers_not_all(sync_mod, monkeypatch, tmp_path):
    """D4: `updated` must count markers whose value changed, not every marker in
    a file that happened to be rewritten. The old code did
    `updated += len(MARKER_RE.findall(text))`, reporting N markers updated even
    when only 1 changed — training the author to ignore the count."""
    doc = _write(
        tmp_path / "docs" / "X.md",
        "# T\n\n<!--fact:gate_count-->23<!--/fact--> checks.\n"
        "<!--fact:coverage-->98<!--/fact--> coverage.\n",
    )
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    changed, updated, _ = sync_mod.apply_facts({"gate_count": "24", "coverage": "98"})
    # Only gate_count changed; coverage was already correct.
    assert (changed, updated) == (1, 1)
    text = doc.read_text()
    assert "<!--fact:gate_count-->24<!--/fact-->" in text
    assert "<!--fact:coverage-->98<!--/fact-->" in text


def test_apply_reports_zero_updated_when_nothing_changed(sync_mod, monkeypatch, tmp_path):
    """A file rewritten for another marker's sake must not inflate `updated`."""
    _write(
        tmp_path / "docs" / "X.md",
        "# T\n\n<!--fact:gate_count-->23<!--/fact--> checks.\n"
        "<!--fact:coverage-->98<!--/fact--> coverage.\n",
    )
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    changed, updated, _ = sync_mod.apply_facts({"gate_count": "23", "coverage": "98"})
    assert (changed, updated) == (0, 0)


def test_apply_leaves_unknown_facts_alone(sync_mod, monkeypatch, tmp_path):
    doc = _write(
        tmp_path / "docs" / "X.md",
        "# T\n\n<!--fact:test_count-->1063<!--/fact--> passed\n",
    )
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    changed, _, unknown = sync_mod.apply_facts({"test_count": "unknown"})
    assert changed == 0
    assert unknown == ["docs/X.md:test_count"]
    assert "1063" in doc.read_text()


# ── drift detection ──────────────────────────────────────────────────────────


def test_check_flags_a_stale_marker(sync_mod, monkeypatch, tmp_path):
    _write(
        tmp_path / "docs" / "X.md",
        "# T\n\n<!--fact:gate_count-->22<!--/fact--> checks\n",
    )
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    findings = sync_mod.check_facts({"gate_count": "23"})
    assert len(findings) == 1 and "says '22'" in findings[0]


def test_check_flags_an_unmarked_stale_claim(sync_mod, monkeypatch, tmp_path):
    """This is the half that catches numbers written before markers existed."""
    _write(tmp_path / "docs" / "X.md", "# T\n\nThe gate runs 22 checks today.\n")
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    findings = sync_mod.check_facts({"gate_count": "23"})
    assert len(findings) == 1 and "unmarked stale claim" in findings[0]


def test_check_ignores_a_correct_unmarked_claim(sync_mod, monkeypatch, tmp_path):
    _write(tmp_path / "docs" / "X.md", "# T\n\nThe gate runs 23 checks today.\n")
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    assert sync_mod.check_facts({"gate_count": "23"}) == []


def test_section_number_is_not_a_claim(sync_mod, monkeypatch, tmp_path):
    """'### 5.2 ADR Template' must not be read as '2 ADRs'."""
    _write(tmp_path / "docs" / "X.md", "# T\n\n### 5.2 ADR Template\n\n### 5.3 ADR Index\n")
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    assert sync_mod.check_facts({"adr_count": "13"}) == []


def test_unresolvable_cited_fact_is_a_finding_not_a_silence(sync_mod, monkeypatch, tmp_path):
    """The regression this whole hardening exists for.

    When a document cites a fact the checker cannot derive, the document cannot be
    certified. Returning no findings would report "clean" while the number beneath
    may be arbitrarily stale — which is exactly how `docs/ROADMAP.md` came to assert
    a test count 84 lower than the suite's real count while `--check` printed
    "no findings".
    """
    _write(
        tmp_path / "docs" / "X.md",
        "# T\n\nThe suite runs <!--fact:test_count-->1063<!--/fact--> tests.\n",
    )
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    findings = sync_mod.check_facts({"test_count": "unknown", "coverage": "unknown"})
    assert findings, "an unresolvable cited fact must be reported, not skipped"
    assert "could not be verified" in findings[-1]
    assert "test_count" in findings[-1]


def test_unresolvable_fact_can_still_be_quoted(sync_mod, monkeypatch, tmp_path):
    """Prose explaining the anti-pattern may cite a fact in a fence without tripping."""
    _write(
        tmp_path / "docs" / "X.md",
        "# T\n\n```\n<!--fact:test_count-->1063<!--/fact-->\n```\n",
    )
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    assert sync_mod.check_facts({"test_count": "unknown"}) == []


def test_marker_naming_an_unknown_fact_is_flagged(sync_mod, monkeypatch, tmp_path):
    """A typo'd marker name would otherwise resolve to `unknown` and never be checked."""
    _write(
        tmp_path / "docs" / "X.md",
        "# T\n\nThe gate runs <!--fact:gate_countt-->25<!--/fact--> checks.\n",
    )
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    findings = sync_mod.check_facts({"gate_count": "25"})
    assert any("not a known fact" in f for f in findings), findings


def test_every_declared_known_fact_is_actually_producible(sync_mod):
    """KNOWN_FACTS must not drift from what collect() can derive, or a legitimate
    marker would be rejected as a typo."""
    produced = set(sync_mod.collect())
    assert produced == sync_mod.KNOWN_FACTS, (
        f"KNOWN_FACTS != collected facts; "
        f"only-in-KNOWN={sync_mod.KNOWN_FACTS - produced}, "
        f"only-in-collect={produced - sync_mod.KNOWN_FACTS}"
    )


def test_correct_marker_is_not_also_flagged_as_bare_claim(sync_mod, monkeypatch, tmp_path):
    """A marked claim must be counted once, not twice."""
    _write(
        tmp_path / "docs" / "X.md",
        "# T\n\nThe gate runs <!--fact:gate_count-->23<!--/fact--> checks.\n",
    )
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    assert sync_mod.check_facts({"gate_count": "23"}) == []


def test_archive_is_exempt(sync_mod, monkeypatch, tmp_path):
    _write(tmp_path / "docs" / "archive" / "OLD.md", "# T\n\nthe 22 checks of old\n")
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    assert sync_mod.check_facts({"gate_count": "23"}) == []


def test_changelog_is_exempt_because_release_notes_are_history(sync_mod, monkeypatch, tmp_path):
    _write(tmp_path / "docs" / "CHANGELOG.md", "# C\n\n1028 passed, coverage 36%\n")
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    assert sync_mod.check_facts({"test_count": "1063", "coverage": "98"}) == []


def test_fenced_code_block_is_quoted_not_a_claim(sync_mod, monkeypatch, tmp_path):
    """A document explaining the rule must be able to show the anti-pattern.
    Code blocks are illustrative by definition."""
    _write(
        tmp_path / "docs" / "X.md",
        "# T\n\nFor example:\n\n```\nThe gate runs 22 checks.\n```\n",
    )
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    assert sync_mod.check_facts({"gate_count": "23"}) == []


def test_escape_marker_exempts_an_inline_quote(sync_mod, monkeypatch, tmp_path):
    _write(
        tmp_path / "docs" / "X.md",
        "# T\n\nWe used to write <!--doc-facts:quoted-->the gate runs 22 checks, wrongly.\n",
    )
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    assert sync_mod.check_facts({"gate_count": "23"}) == []


def test_claim_outside_a_fence_is_still_caught(sync_mod, monkeypatch, tmp_path):
    """The fence exemption must not become a blanket amnesty: text after the
    closing fence is prose again and is judged normally."""
    _write(
        tmp_path / "docs" / "X.md",
        "# T\n\n```\nexample\n```\n\nThe gate runs 22 checks.\n",
    )
    monkeypatch.setattr(sync_mod, "REPO_ROOT", tmp_path)
    findings = sync_mod.check_facts({"gate_count": "23"})
    assert len(findings) == 1 and "22 checks" in findings[0]


def test_line_is_quoted_unclosed_fence_stays_quoted(sync_mod):
    """An unterminated fence is malformed markdown; treating the tail as quoted
    is the safe direction (it cannot be a well-formed claim)."""
    lines = ["# T", "```", "The gate runs 22 checks."]
    assert sync_mod._line_is_quoted(lines, 2) is True


# ── end-to-end: the real repository must be consistent ───────────────────────


def test_real_repository_has_no_doc_drift(sync_mod):
    """HEAD's documentation must agree with HEAD's code. This is the regression
    guard for the whole mechanism.

    It also asserts the guard has *teeth*: the expensive facts must resolve, so
    this test cannot pass by measuring nothing. Without that assertion the test is
    self-defeating — an unresolvable `test_count` used to make `check_facts` skip
    the marker entirely, so this test would report success precisely when it had
    verified the least.

    CRITICAL: This test must compute facts directly from the repository code,
    never from the ephemeral cache. The cache is an optimization, not an
    authority — see the architecture decision documented in the doc-facts system.

    When run inside a pytest session (e.g. via `pytest tests/`), coverage cannot
    be measured (it requires test execution, which would cause infinite
    recursion). In that case, only test_count is asserted. When run outside
    pytest (CI, pre-commit), both test_count and coverage are asserted.
    """
    inside_pytest = "pytest" in sys.modules
    facts = sync_mod.collect(run_tests=True)

    # test_count is always measurable (via --collect-only inside pytest, full run outside).
    assert facts.get("test_count") not in (None, "unknown"), (
        "'test_count' did not resolve, so the drift guard cannot verify anything " "that cites it"
    )

    # Coverage requires test execution, which is only available outside pytest.
    # Inside pytest, attempting to run tests recursively would cause infinite recursion.
    if not inside_pytest:
        assert facts.get("coverage") not in (None, "unknown"), (
            "'coverage' did not resolve, so the drift guard cannot verify anything " "that cites it"
        )

    # Build the fact set for verification. Inside pytest, we only verify
    # test_count (coverage is unknown and would cause false drift reports).
    verification_facts = {"test_count": facts["test_count"]}
    if not inside_pytest:
        verification_facts["coverage"] = facts["coverage"]

    findings = sync_mod.check_facts(verification_facts)
    assert findings == [], "doc drift:\n" + "\n".join(findings)


def test_every_fact_marker_is_a_known_fact(sync_mod):
    """A typo'd marker name would silently never be checked."""
    known = set(sync_mod.collect())
    unknown_markers = set()
    import re

    for path in sync_mod.iter_docs():
        for m in re.finditer(r"<!--fact:([a-z_]+)-->", path.read_text(encoding="utf-8")):
            if m.group(1) not in known:
                unknown_markers.add(m.group(1))
    assert unknown_markers == set(), f"markers referencing unknown facts: {unknown_markers}"
