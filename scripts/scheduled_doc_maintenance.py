#!/usr/bin/env python3
"""Scheduled documentation maintenance — the local equivalent of USA's
docs-link-check.yml and docs-review.yml workflows.

Runs on a cron schedule (every 15 days) and:
  1. Checks every external link in the docs for hard-dead URLs (404/410/DNS).
  2. Determines which documents are due for a semantic review (cadence from
     DOC-GOVERNANCE.md §7, derived from git history — never a hand-maintained date).
  3. Opens ONE deduped GitHub issue per run naming the dead links and the
     docs due for review, so a human or agent can act on a bounded packet.

This is the only place in the doc pipeline that uses the network. The
audit path (ci_gate.py) stays offline; this runs on its own schedule.

Usage:
    python scripts/scheduled_doc_maintenance.py              # run + report
    python scripts/scheduled_doc_maintenance.py --check-only # dry run, no issue
"""

from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_LINKS = REPO_ROOT / "scripts" / "check_links.py"
DOC_REVIEW = REPO_ROOT / "scripts" / "doc_review_due.py"


def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=300)
    return proc.returncode, proc.stdout, proc.stderr


def _gh_issue_open(title: str, body: str, labels: list[str]) -> bool:
    """Open a GitHub issue, or comment on an existing open one with the same title."""
    import shutil

    if not shutil.which("gh"):
        return False
    try:
        # Check for existing open issue with same title
        existing = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--search",
                f"{title} in:title",
                "--state",
                "open",
                "--json",
                "number",
                "--jq",
                ".[0].number",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if existing.returncode == 0 and existing.stdout.strip():
            number = existing.stdout.strip()
            subprocess.run(
                ["gh", "issue", "comment", number, "--body", body],
                cwd=str(REPO_ROOT),
                capture_output=True,
                timeout=30,
            )
            return True
        # Create new issue
        subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--title",
                title,
                "--label",
                ",".join(labels),
                "--body",
                body,
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            timeout=30,
        )
        return True
    except (subprocess.TimeoutExpired, OSError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check-only", action="store_true", help="dry run, do not open issues")
    args = ap.parse_args()

    now = datetime.now(UTC).strftime("%Y-%m-%d")
    print(f"=== Scheduled doc maintenance — {now} ===\n")

    # 1. External link check
    print("--- External link check ---")
    rc, out, err = _run(
        [sys.executable, str(CHECK_LINKS), "--json"],
        REPO_ROOT,
    )
    dead: list[dict] = []
    if rc in (0, 1):
        try:
            data = json.loads(out) if out.strip() else {}
            # check_links.py --json returns {results: {url: {verdict, detail, file}}}
            results = data.get("results", data) if isinstance(data, dict) else {}
            for url, info in results.items():
                if isinstance(info, dict) and info.get("verdict") in ("dead", "hard-dead"):
                    dead.append(
                        {"url": url, "detail": info.get("detail", ""), "file": info.get("file", "")}
                    )
        except (json.JSONDecodeError, AttributeError):
            pass
    print(f"  hard-dead links: {len(dead)}")
    for link in dead[:10]:
        print(f"    {link['url'][:80]}")
    if len(dead) > 10:
        print(f"    ... ({len(dead) - 10} more)")

    # 2. Doc review due
    print("\n--- Documents due for review ---")
    rc, out, err = _run(
        [sys.executable, str(DOC_REVIEW), "--json"],
        REPO_ROOT,
    )
    due: list[dict] = []
    if rc == 0:
        with contextlib.suppress(json.JSONDecodeError):
            due = json.loads(out) if out.strip() else []
    print(f"  documents due: {len(due)}")
    for doc in due[:10]:
        print(f"    {doc.get('doc', '?')} (cadence {doc.get('cadence_days', '?')}d)")
    if len(due) > 10:
        print(f"    ... ({len(due) - 10} more)")

    if args.check_only:
        print("\n--check-only: no issue opened.")
        return 0

    if not dead and not due:
        print("\nNothing to report — docs are healthy.")
        return 0

    # 3. Open or update a single deduped issue
    title = "[automation] scheduled documentation maintenance"
    sections = [f"Run: {now}"]
    if dead:
        lines = [f"## Dead links ({len(dead)})", ""]
        for link in dead:
            lines.append(f"- `{link.get('url', '?')}` (in `{link.get('file', '?')}`)")
        sections.append("\n".join(lines))
    if due:
        lines = [f"## Documents due for review ({len(due)})", ""]
        for doc in due:
            lines.append(
                f"- [ ] `{doc.get('doc', '?')}` — cadence {doc.get('cadence_days', '?')}d, "
                f"last reviewed {doc.get('last_reviewed', '?')}"
            )
        sections.append("\n".join(lines))
    body = "\n\n".join(sections) + (
        "\n\n<sub>From `scripts/scheduled_doc_maintenance.py` "
        "(runs every 15 days via cron).</sub>"
    )

    if _gh_issue_open(title, body, ["documentation", "automation"]):
        print(f"\nIssue opened/updated: {title}")
    else:
        print("\nCould not open GitHub issue (gh CLI missing or auth issue).")
        print("Report:\n" + body)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
