#!/usr/bin/env python3
"""Scheduled staleness review for the documents that cannot be auto-synced.

The fact-sync mechanism handles everything machine-derivable: counts, versions,
paths, numbers. What it cannot handle is **semantic drift** — a governance or
architecture document that is still structurally valid and numerically accurate,
but no longer describes how the system actually works, or describes a practice
nobody follows.

That needs a human-or-agent re-read, on a cadence. This script decides *which*
documents are due, and produces a bounded review packet so the re-read is a
short, concrete task rather than "read everything".

Cadence is declared per document in `docs/DOC-GOVERNANCE.md` §7 by class; this
script encodes the mapping and uses git history for the last actual review (the
last commit that touched the doc), not a hand-maintained date — hand-maintained
dates rot, which is the whole problem.

Usage:
    python scripts/doc_review_due.py              # human summary
    python scripts/doc_review_due.py --json       # machine list
    python scripts/doc_review_due.py --packet     # markdown review packet
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Days between mandatory re-reads, by document class. Mirrors DOC-GOVERNANCE.md §7.
CADENCE_DAYS: dict[str, int] = {
    "docs/ARCHITECTURE.md": 90,
    "docs/GOVERNANCE.md": 90,
    "docs/CI-GATE-SOTA.md": 90,
    "docs/CI-TOKEN-PERMISSIONS.md": 90,
    "docs/CAPABILITY_TRACKER.md": 90,
    "docs/API_CONTRACT.md": 90,
    "docs/CAPABILITY-CONTRACT.md": 90,
    "docs/DOC-GOVERNANCE.md": 90,
    "docs/ROADMAP.md": 30,
    "docs/ACCEPTED_RISKS.md": 30,
    "docs/DEVELOPMENT.md": 180,
    "docs/CONFIG.md": 180,
    "docs/DATABASE.md": 180,
    "docs/LLM.md": 180,
    "docs/MEMORY.md": 180,
    "docs/TOOLS.md": 180,
    "docs/DEBUGGING.md": 365,
}

DEFAULT_CADENCE = 180

# Never reviewed on a cadence.
EXEMPT_PREFIXES = ("docs/archive/", "docs/adr/", "docs/timelines/")
EXEMPT_FILES = {
    "docs/CHANGELOG.md",
    "docs/DEBUGGING.md",
    "docs/DECISIONS-AUTONOMOUS-2026-09-10.md",
    "docs/AUDIT-USAT.md",
    "docs/SPRINT_1_2_COMPLETION.md",
    "docs/SYMBOL_LINEAGE.md",
}


def _git(*args: str) -> str:
    try:
        r = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60
        )
        return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def last_touched(rel: str) -> date | None:
    """Date of the last commit that changed this document.

    Deliberately git-based: a 'Last Updated' line is a claim a human maintains by
    hand, and hand-maintained dates are exactly what drifts.
    """
    out = _git("log", "-1", "--format=%cs", "--", rel)
    if not out:
        return None
    try:
        return date.fromisoformat(out.splitlines()[0])
    except ValueError:
        return None


def commits_since(since_iso: str) -> int | None:
    """How many commits have touched the tree since a date.

    Reported as *context* on a review row, never used as review evidence. A
    document that has been mechanically edited many times since it was last read
    against the implementation is the strongest candidate for a re-read, which is
    precisely why the count is surfaced rather than the date being trusted.
    """
    out = _git("rev-list", "--count", f"--since={since_iso}", "HEAD")
    try:
        return int(out.splitlines()[0])
    except (IndexError, ValueError):
        return None


def reviewed_in_text(text: str) -> date | None:
    """The explicit `**Reviewed**: YYYY-MM-DD` line — the ONLY signal that resets
    the semantic-review clock.

    This is deliberately the sole authority. A git commit records that *something*
    changed, which is not the same as a human or agent re-reading the document
    against the implementation. A typo fix, a marker sync (`sync_doc_facts --apply`
    rewrites prose on every commit that moves a count), or a formatting pass all
    touch the file without anyone having judged whether the document is still true.

    Using the last-touched date as review evidence would therefore let mechanical
    edits silently mark documents as reviewed — the exact failure this script exists
    to prevent. Git history is still reported, as *context* for the reviewer.

    A **future** date is rejected. It cannot be evidence of a review that has
    happened, and accepting it would let a typo (2026-12-13 for 2026-09-13) park a
    document permanently out of the review queue. Rejecting it fails safe: the
    document stays due.
    """
    today = datetime.now(UTC).date()
    for line in text.splitlines()[:25]:
        if "Reviewed" in line and ":" in line:
            tail = line.split(":", 1)[1].strip()
            token = tail.split()[0].strip("*_`()[]")
            try:
                parsed = date.fromisoformat(token)
            except ValueError:
                continue
            if parsed > today:
                continue
            return parsed
    return None


def iter_docs() -> list[Path]:
    return sorted((REPO_ROOT / "docs").rglob("*.md"))


def assess(today: date | None = None) -> list[dict[str, object]]:
    """Which living documents are due for a deliberate semantic re-read?

    The clock is driven by **explicit review evidence only** (`**Reviewed**`), never
    by the last commit. See `reviewed_in_text` for why: git records that something
    changed, which is not a semantic re-read, and treating it as one lets a typo fix
    or an automatic marker sync silently reset a document's review status.

    `last_touched` and `commits_since` are reported as *context* for the reviewer —
    "this document has been mechanically edited 6 times since it was last reviewed"
    is exactly the signal that it needs reading — but they never move the clock.

    A document with no `**Reviewed**` line at all is due. That is the safe direction:
    an unclaimed review is not a review, and this is a prompt for work, not a
    judgement that the document is wrong.
    """
    today = today or datetime.now(UTC).date()
    rows: list[dict[str, object]] = []
    for p in iter_docs():
        rel = str(p.relative_to(REPO_ROOT))
        if rel.startswith(EXEMPT_PREFIXES) or rel in EXEMPT_FILES:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if "**Status**: HISTORICAL" in text or "**Status**: SNAPSHOT" in text:
            continue
        cadence = CADENCE_DAYS.get(rel, DEFAULT_CADENCE)
        touched = last_touched(rel)
        reviewed = reviewed_in_text(text)

        # The clock: explicit evidence only.
        age = (today - reviewed).days if reviewed else None
        due = age is None or age > cadence

        # Context for the reviewer, never the clock.
        edits_since = commits_since(reviewed.isoformat()) if reviewed else None

        rows.append(
            {
                "doc": rel,
                "cadence_days": cadence,
                "last_reviewed": reviewed.isoformat() if reviewed else None,
                "review_evidence": "**Reviewed**" if reviewed else None,
                "age_days": age,
                "due": due,
                "overdue_by": (age - cadence) if age is not None else None,
                "last_modified": touched.isoformat() if touched else None,
                "edits_since_review": edits_since,
            }
        )
    # Most overdue first; documents never reviewed sort ahead of everything, since
    # "no evidence at all" is a weaker state than "evidence that is old".
    rows.sort(key=lambda r: -(r["overdue_by"] if isinstance(r["overdue_by"], int) else 10**6))
    return rows


def packet(rows: list[dict[str, object]]) -> str:
    due = [r for r in rows if r["due"]]
    out = [
        "# Documentation staleness review packet",
        "",
        f"Generated: {datetime.now(UTC).date().isoformat()}",
        "",
        f"{len(due)} of {len(rows)} living documents are due for a re-read.",
        "",
        "This packet asks for a **semantic** re-read: deciding whether a document",
        "still describes the system, is still useful, and is still complete. That is",
        "a judgement no check in this repository can make — which is why it is a",
        "prompt for a person rather than a gate.",
        "",
        "For each, answer three questions and record the outcome **in the doc**:",
        "",
        "1. **Still true?** Does it describe how the system works at `HEAD`?",
        "2. **Still useful?** Does anyone act on it, or is it decoration?",
        "3. **Still complete?** Has something been added that it now omits?",
        "",
        "Then set `**Last Updated**: <today>` (the content changed today) and add",
        "**`**Reviewed**: <today>`**. Only `**Reviewed**` resets the review clock —",
        "it is the explicit claim that a semantic re-read happened. `**Last Updated**`",
        "records an edit and does *not* reset the clock, because a typo fix or an",
        "automatic marker sync is an edit, not a review.",
        "",
        "If a re-read concludes the document is still correct, adding `**Reviewed**`",
        "is the complete and correct outcome. Nothing needs to change.",
        "",
        "---",
        "",
    ]
    for r in due:
        age = r["age_days"]
        over = r["overdue_by"]
        edits = r["edits_since_review"]
        age_s = f"{age} days old" if age is not None else "never reviewed"
        over_s = f" (overdue by {over} days)" if isinstance(over, int) and over > 0 else ""
        out.append(f"## {r['doc']}")
        out.append("")
        out.append(f"- cadence: {r['cadence_days']} days")
        out.append(
            f"- last reviewed: {r['last_reviewed'] or 'no recorded review'} — {age_s}{over_s}"
        )
        if isinstance(edits, int):
            out.append(
                f"- edited {edits} time(s) in the tree since that review "
                f"(mechanical edits do not count as review; they are why this is due)"
            )
        out.append(
            f"- re-read with: `git log -5 --oneline -- {r['doc']}` then compare against `HEAD`"
        )
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--packet", action="store_true")
    ap.add_argument("--due-only", action="store_true")
    args = ap.parse_args()

    rows = assess()
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if args.packet:
        print(packet(rows))
        return 0

    due = [r for r in rows if r["due"]]
    print(f"doc_review_due: {len(due)} of {len(rows)} living document(s) due for re-read")
    for r in due:
        age = r["age_days"]
        age_s = f"{age}d" if age is not None else "never"
        print(f"  DUE  {r['doc']:<45} age={age_s:<7} cadence={r['cadence_days']}d")
    if not due:
        print("  nothing overdue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
