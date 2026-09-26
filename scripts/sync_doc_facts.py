#!/usr/bin/env python3
"""Keep machine-derivable numbers in the docs true to the code.

Two jobs:

``--apply``
    Rewrite every ``<!--fact:name-->value<!--/fact-->`` marker with the value
    derived from the repository. Use this after changing the code so the docs
    catch up in the same commit.

``--check`` (CI gate)
    Fail when any marker's committed value disagrees with reality, and fail when
    a **bare** (unmarked) numeric claim is recognised as a stale fact. The second
    part is what catches numbers written before markers existed — otherwise the
    convention only protects claims added after it.

Why markers instead of prose rewriting: "22 checks" in six documents cannot be
safely regex-replaced in arbitrary prose ("the 22 checks of the pipeline"). A
marker is unambiguous, greppable and diffable.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doc_facts import MARKER_RE, REPO_ROOT, collect, collect_cheap  # noqa: E402

EXPENSIVE_FACTS = ("test_count", "coverage")


def _full_head() -> str:
    """Full HEAD sha of the tree being described (empty when unavailable)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.strip()


def reconcile_injected_facts(injected: object) -> dict[str, str]:
    """Merge an externally supplied snapshot with live cheap facts.

    The ``--facts-json`` fast path exists to skip pytest, but a snapshot is a
    claim about a PAST tree. Applying it blindly writes stale numbers as
    current truth (observed in the wild: ``test_count`` 1694 written while the
    suite collected 1746). So: cheap facts are always recomputed live
    (milliseconds), and expensive measurements survive ONLY when the
    snapshot's commit matches HEAD. Otherwise they become ``"unknown"`` —
    ``apply_facts`` then skips those markers and ``check_facts`` reports
    explicit cannot-verify findings instead of passing on a lie.
    """
    facts: dict[str, str] = {}
    if isinstance(injected, dict):
        facts = {str(k): str(v) for k, v in injected.items()}
    snapshot_commit = facts.get("commit", "")
    facts.update(collect_cheap())  # cheap facts always live, including commit
    # NOTE: collect_cheap reports a SHORT commit while caches carry the full
    # sha — compare by prefix in either direction, never by equality.
    head = _full_head()
    if (
        not snapshot_commit
        or not head
        or not (head.startswith(snapshot_commit) or snapshot_commit.startswith(head))
    ):
        for name in EXPENSIVE_FACTS:
            facts[name] = "unknown"
    return facts


BACKTICK_FACT_RE = re.compile(r"<!--fact:([a-z_]+)-->(.*?)<!--/fact-->", re.DOTALL)

# Bare, unmarked claims that should carry a marker. Kept narrow and explicit so
# this stays a drift alarm, not a style linter.
# (regex, fact name) — the regex must capture the NUMBER in group 1.
#
# The negative lookbehind on `[.\d]` matters: "### 5.2 ADR Template" is a section
# number, not a claim about how many ADRs exist.
BARE_CLAIMS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<![\d.])\b(\d{1,3})\s+(?:CI\s+)?(?:checks|gates)\b"), "gate_count"),
    (re.compile(r"(?<![\d.])\b(\d{1,3})\s+ADRs?\b"), "adr_count"),
    (re.compile(r"(?<![\d.])\b(\d{1,3})\s+(?:published\s+)?contexts\b"), "context_count"),
    (re.compile(r"(?<![\d.])\b(\d{3,4})\s+(?:tests?\s+)?passed\b"), "test_count"),
    (re.compile(r"(?<![\d.])\b(\d{3,4})\s+tests?\b"), "test_count"),
]

# Documents that are allowed to contain historical numbers without markers:
# they describe a past state on purpose and must NOT be rewritten.
EXEMPT_PREFIXES = (
    "docs/archive/",
    # An ADR is the one place a stale number is *correct*. Its Context section
    # records what was true when the decision was taken — ADR-014 quotes "22 checks"
    # precisely because that was the value that drifted. Rewriting it would falsify
    # the record the ADR exists to keep, and an ADR must never be edited to look
    # right in hindsight (docs/DOC-GOVERNANCE.md §10, type `adr`).
    "docs/adr/",
)
EXEMPT_FILES = {
    "docs/CHANGELOG.md",  # release notes are a historical record
    "docs/DEBUGGING.md",  # historical symptom log
    "docs/DECISIONS-AUTONOMOUS-2026-09-10.md",  # dated decision snapshot
    "docs/AUDIT-USAT.md",  # dated audit snapshot
    "docs/SPRINT_1_2_COMPLETION.md",  # dated sprint record
    "docs/ACCEPTED_RISKS.md",  # risk rows carry dated measurements
}

# An author must be able to *quote* a stale claim to explain the rule — this very
# document explains what the detector catches. A fenced code block, or a line
# carrying this escape, is quoted material rather than a claim.
ESCAPE = "<!--doc-facts:quoted-->"
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _line_is_quoted(lines: list[str], idx: int) -> bool:
    """True when the line at ``idx`` is illustrative, not an assertion.

    Two principled cases: inside a fenced code block (code is illustrative), or
    carrying the explicit ESCAPE comment (the author is quoting an anti-pattern).
    """
    if ESCAPE in lines[idx]:
        return True
    open_fence: str | None = None
    for i in range(idx):
        m = FENCE_RE.match(lines[i])
        if not m:
            continue
        if open_fence is None:
            open_fence = m.group(1)
        elif m.group(1) == open_fence:
            open_fence = None
    return open_fence is not None


def iter_docs() -> list[Path]:
    out = list((REPO_ROOT / "docs").rglob("*.md"))
    out += list(REPO_ROOT.glob("*.md"))
    return sorted(out)


# Facts a document is allowed to cite. Anything else is a typo, and a typo'd
# marker name would silently never be checked (the value would resolve to
# `unknown` and be skipped forever).
KNOWN_FACTS = frozenset(
    {
        "version",
        "commit",
        "gate_count",
        "context_count",
        "adr_count",
        "board_count",
        "cadence_fast",
        "cadence_default",
        "cadence_quarterly",
        "cadence_historical",
        "doc_count",
        "python_requires",
        "test_count",
        "coverage",
    }
)


def is_exempt(p: Path) -> bool:
    rel = str(p.relative_to(REPO_ROOT))
    return rel.startswith(EXEMPT_PREFIXES) or rel in EXEMPT_FILES


def apply_facts(facts: dict[str, str]) -> tuple[int, int, list[str]]:
    """Rewrite marker values. Returns (files_changed, markers_updated, unknown)."""
    changed = updated = 0
    unknown: list[str] = []
    for path in iter_docs():
        if is_exempt(path):
            continue
        text = original = path.read_text(encoding="utf-8", errors="replace")
        for name in dict.fromkeys(MARKER_RE.findall(text)):
            name = name[0] if isinstance(name, tuple) else name
            value = facts.get(name, "unknown")
            if value == "unknown":
                unknown.append(f"{path.relative_to(REPO_ROOT)}:{name}")
                continue
            for marker in MARKER_RE.finditer(text):
                if marker.group(1) != name:
                    continue
                if marker.group(2) == value:
                    # Already correct — not a rewrite, not a change reported.
                    continue
                before = marker.group(0)
                after = f"<!--fact:{name}-->{value}<!--/fact-->"
                text = text[: marker.start()] + after + text[marker.end() :]
                if before != after:
                    updated += 1
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed += 1
    return changed, updated, unknown


def check_facts(facts: dict[str, str]) -> list[str]:
    """Every number a doc asserts must be verifiable against the repository.

    The rule that matters, and the one this function previously got wrong: an
    **unresolvable** fact is a finding, not a pass. If a document cites
    `test_count` and the fact cannot be derived, the checker cannot say the
    document is true — it can only say it does not know. Reporting that silence
    as "no findings" is the worst possible outcome, because it *looks* like
    verification while the number underneath may be arbitrarily stale.

    That is not hypothetical. `coverage`/`test_count` are expensive and read from
    a gate-written cache; when the cache was unprovenanced or absent they resolved
    to `unknown`, `check_facts` skipped them, and `docs/ROADMAP.md` asserted a
    test count 84 lower than the suite's real count while this checker printed
    "no findings — every marked fact matches the repository". A blind spot that
    reports clean is worse than no check, so an unresolved *cited* fact is now a
    blocking finding naming the marker and why it is unresolvable.
    """
    findings: list[str] = []
    cited_unknown: list[str] = []
    for path in iter_docs():
        rel = str(path.relative_to(REPO_ROOT))
        if is_exempt(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()

        # 0. a marker naming a fact that does not exist is a typo, and a typo would
        #    otherwise resolve to `unknown` and be skipped forever.
        for m in MARKER_RE.finditer(text):
            if m.group(1) not in KNOWN_FACTS:
                line = text[: m.start()].count("\n") + 1
                findings.append(
                    f"{rel}:{line}: marker '{m.group(1)}' is not a known fact "
                    f"— see scripts/doc_facts.py for the list"
                )

        # 1. marked values must match
        for m in MARKER_RE.finditer(text):
            name, committed = m.group(1), m.group(2).strip()
            if name not in facts:
                # Fact not in the provided snapshot; skip (caller chose not to verify this fact).
                continue
            actual = facts[name]
            if actual == "unknown":
                # The document asserts a value we cannot verify. That is a finding,
                # not a silence — unless the line is quoting the anti-pattern.
                line = text[: m.start()].count("\n") + 1
                if _line_is_quoted(lines, line - 1):
                    continue
                cited_unknown.append(f"{rel}:{line}: fact '{name}'")
                continue
            if committed != actual:
                line = text[: m.start()].count("\n") + 1
                if _line_is_quoted(lines, line - 1):
                    continue
                findings.append(
                    f"{rel}:{line}: fact '{name}' says {committed!r} but the repo says {actual!r} "
                    f"— run scripts/sync_doc_facts.py --apply"
                )

        # 2. bare claims that contradict reality must be marked
        for rx, name in BARE_CLAIMS:
            if name not in facts:
                # Fact not in the provided snapshot; skip.
                continue
            actual = facts[name]
            if actual == "unknown":
                continue
            for m in rx.finditer(text):
                if m.group(1) == actual:
                    continue
                # ignore a number that is already inside a fact marker
                line = text[: m.start()].count("\n") + 1
                if any(fm.start() <= m.start() < fm.end() for fm in MARKER_RE.finditer(text)):
                    continue
                # ignore quoted/illustrative material (fenced code, or an explicit
                # escape) — prose explaining the rule must be able to show the
                # anti-pattern without tripping the rule itself.
                if _line_is_quoted(lines, line - 1):
                    continue
                findings.append(
                    f"{rel}:{line}: unmarked stale claim {m.group(0)!r} (repo says {actual}) "
                    f"— wrap it in <!--fact:{name}-->{actual}<!--/fact-->"
                )

    # Unresolvable cited facts are reported as a single grouped finding. They mean
    # the checker could not verify the document — not that the document is wrong —
    # and the fix is to produce the measurement (run the gate), not to edit prose.
    if cited_unknown:
        findings.append(
            f"{len(cited_unknown)} citation(s) could not be verified because the fact(s) "
            f"are unresolvable — the checker cannot certify a document it cannot measure. "
            f"Run the gate (`scripts/ci_gate.py --with-coverage`) so "
            f"`.governance/doc_facts.json` carries a measurement for this commit: "
            + ", ".join(cited_unknown[:10])
            + (" …" if len(cited_unknown) > 10 else "")
        )
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true", help="rewrite marker values from the repo")
    g.add_argument("--check", action="store_true", help="fail on stale markers/bare claims")
    g.add_argument(
        "--sync",
        action="store_true",
        help="compute facts once, apply to docs, verify, and write cache (one pytest run)",
    )
    ap.add_argument("--run-tests", action="store_true", help="compute test facts by running them")
    ap.add_argument(
        "--facts-json",
        help="use the provided JSON fact snapshot instead of computing (for CI reuse)",
    )
    args = ap.parse_args()

    if args.sync:
        facts = collect(run_tests=True)
        changed, updated, unknown = apply_facts(facts)
        print(f"sync_doc_facts: rewrote {updated} marker value(s) in {changed} file(s)")
        if unknown:
            print(f"  skipped {len(unknown)} marker(s) with no derivable value (unknown):")
            for u in unknown[:15]:
                print(f"    {u}")
        findings = check_facts(facts)
        print(f"sync_doc_facts: checked {len(iter_docs())} markdown file(s)")
        if findings:
            print(f"\n{len(findings)} finding(s):\n")
            for f in findings:
                print("  -", f)
            return 1
        print("no findings — documentation is consistent with the repository")
        return 0

    if args.facts_json:
        import json

        facts = reconcile_injected_facts(json.loads(args.facts_json))
    else:
        facts = collect(run_tests=args.run_tests)

    if args.apply:
        changed, updated, unknown = apply_facts(facts)
        print(f"sync_doc_facts: rewrote {updated} marker value(s) in {changed} file(s)")
        if unknown:
            print(f"  skipped {len(unknown)} marker(s) with no derivable value (unknown):")
            for u in unknown[:15]:
                print(f"    {u}")
        return 0

    findings = check_facts(facts)
    print(f"sync_doc_facts: checked {len(iter_docs())} markdown file(s)")
    if findings:
        print(f"\n{len(findings)} finding(s):\n")
        for f in findings:
            print("  -", f)
        return 1
    print("no findings — every marked fact matches the repository")
    return 0


if __name__ == "__main__":
    sys.exit(main())
