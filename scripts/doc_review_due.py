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


def reviewed_in_text(text: str) -> date | None:
    """Honour an explicit `**Reviewed**: YYYY-MM-DD` line when present — that is a
    deliberate acknowledgement of a re-read, stronger evidence than a commit."""
    for line in text.splitlines()[:25]:
        if "Reviewed" in line and ":" in line:
            tail = line.split(":", 1)[1].strip()
            token = tail.split()[0].strip("*_`()[]")
            try:
                return date.fromisoformat(token)
            except ValueError:
                continue
    return None


def iter_docs() -> list[Path]:
    return sorted((REPO_ROOT / "docs").rglob("*.md"))


def assess(today: date | None = None) -> list[dict[str, object]]:
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
        explicit = reviewed_in_text(text)
        basis = max([d for d in (touched, explicit) if d], default=None)
        age = (today - basis).days if basis else None
        rows.append(
            {
                "doc": rel,
                "cadence_days": cadence,
                "last_reviewed": basis.isoformat() if basis else None,
                "age_days": age,
                "due": age is None or age > cadence,
                "overdue_by": (age - cadence) if age is not None else None,
            }
        )
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
        "For each, answer three questions and record the outcome **in the doc**:",
        "",
        "1. **Still true?** Does it describe how the system works at `HEAD`?",
        "2. **Still useful?** Does anyone act on it, or is it decoration?",
        "3. **Still complete?** Has something been added that it now omits?",
        "",
        "Then set `**Last Updated**: <today>` and, if you re-read it against the",
        "code, add `**Reviewed**: <today>` (that is what resets this clock).",
        "",
        "---",
        "",
    ]
    for r in due:
        age = r["age_days"]
        over = r["overdue_by"]
        age_s = f"{age} days old" if age is not None else "never reviewed"
        over_s = f" (overdue by {over} days)" if isinstance(over, int) and over > 0 else ""
        out.append(f"## {r['doc']}")
        out.append("")
        out.append(f"- cadence: {r['cadence_days']} days")
        out.append(f"- last reviewed: {r['last_reviewed'] or 'unknown'} — {age_s}{over_s}")
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
