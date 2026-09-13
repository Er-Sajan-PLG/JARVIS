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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doc_facts import MARKER_RE, REPO_ROOT, collect  # noqa: E402

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
EXEMPT_PREFIXES = ("docs/archive/",)
EXEMPT_FILES = {
    "docs/CHANGELOG.md",  # release notes are a historical record
    "docs/DEBUGGING.md",  # historical symptom log
    "docs/DECISIONS-AUTONOMOUS-2026-09-10.md",  # dated decision snapshot
    "docs/AUDIT-USAT.md",  # dated audit snapshot
    "docs/SPRINT_1_2_COMPLETION.md",  # dated sprint record
    "docs/ACCEPTED_RISKS.md",  # risk rows carry dated measurements
}


def iter_docs() -> list[Path]:
    out = list((REPO_ROOT / "docs").rglob("*.md"))
    out += list(REPO_ROOT.glob("*.md"))
    return sorted(out)


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
            text = MARKER_RE.sub(
                lambda m, n=name, v=value: f"<!--fact:{n}-->{v}<!--/fact-->"
                if m.group(1) == n
                else m.group(0),
                text,
            )
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed += 1
            updated += len(MARKER_RE.findall(text))
    return changed, updated, unknown


def check_facts(facts: dict[str, str]) -> list[str]:
    findings: list[str] = []
    for path in iter_docs():
        rel = str(path.relative_to(REPO_ROOT))
        if is_exempt(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")

        # 1. marked values must match
        for m in MARKER_RE.finditer(text):
            name, committed = m.group(1), m.group(2).strip()
            actual = facts.get(name, "unknown")
            if actual == "unknown":
                continue
            if committed != actual:
                line = text[: m.start()].count("\n") + 1
                findings.append(
                    f"{rel}:{line}: fact '{name}' says {committed!r} but the repo says {actual!r} "
                    f"— run scripts/sync_doc_facts.py --apply"
                )

        # 2. bare claims that contradict reality must be marked
        for rx, name in BARE_CLAIMS:
            actual = facts.get(name, "unknown")
            if actual == "unknown":
                continue
            for m in rx.finditer(text):
                if m.group(1) == actual:
                    continue
                # ignore a number that is already inside a fact marker
                line = text[: m.start()].count("\n") + 1
                if any(fm.start() <= m.start() < fm.end() for fm in MARKER_RE.finditer(text)):
                    continue
                findings.append(
                    f"{rel}:{line}: unmarked stale claim {m.group(0)!r} (repo says {actual}) "
                    f"— wrap it in <!--fact:{name}-->{actual}<!--/fact-->"
                )
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true", help="rewrite marker values from the repo")
    g.add_argument("--check", action="store_true", help="fail on stale markers/bare claims")
    ap.add_argument("--run-tests", action="store_true", help="compute test facts by running them")
    args = ap.parse_args()

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
