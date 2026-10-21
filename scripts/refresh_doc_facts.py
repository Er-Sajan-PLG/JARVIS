#!/usr/bin/env python3
"""Refresh the documentation fact markers on the default branch — as a PR.

Why this exists
---------------
`docs/adr/ADR-014-*.md` makes every derived number in the documentation a
machine-checked marker, and `state/DECISIONS.md` ADR-008 adds the invariant that
stops those markers conflicting on every branch:

    **A branch must never modify a fact marker line. Only the default branch may.**

That makes the conflict impossible by construction — but it also means nothing on
a feature branch will ever correct a value, so the default branch needs a writer
of its own. This script is that writer.

Why the refresh is a local entry point, and the workflow only detects
--------------------------------------------------------------------
`.github/workflows/doc-facts-refresh.yml` runs on `push: main`, on a weekly
schedule and on demand: it reports staleness and opens ONE deduped issue naming
the exact command below. It deliberately does not open the pull request itself,
for two reasons that are properties of GitHub rather than preferences:

1. A pull request opened with a workflow's `GITHUB_TOKEN` does **not** trigger
   `pull_request` workflows, so `ci-gate` — the single required check — would
   never report, and the PR could never merge.
2. `main` requires signed commits (ruleset `protect-main`). A commit pushed by a
   runner is unsigned. GitHub signs the commits *it* creates, not the ones pushed
   to it, and weakening `required_signatures` so automation is convenient is not a
   trade this repository makes.

Run here, the refresh is an ordinary signed commit from the owner's key, pushed
with the owner's credentials, so the PR triggers CI like any other PR. It changes
only marker lines — verified below rather than assumed — and as the sole writer of
those lines it merges cleanly.

Usage
-----
    scripts/refresh_doc_facts.py --check               # is a refresh needed? exit 1 if so
    scripts/refresh_doc_facts.py --open-pr             # sync, verify, push, open the PR
    scripts/refresh_doc_facts.py --open-pr --dry-run   # sync + verify + show the diff, no push

Exit codes: 0 nothing to do / done, 1 a refresh is needed (`--check`), 2 refused.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doc_facts import (  # noqa: E402
    MARKER_RE,
    REFRESH_BRANCH_PREFIX,
    REPO_ROOT,
    collect,
    collect_cheap,
    default_branch,
    resolve_fact_scope,
)
from sync_doc_facts import (  # noqa: E402
    _live_test_count,
    apply_facts,
    check_facts,
    stale_markers,
)


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd or REPO_ROOT), capture_output=True, text=True)


def _blank_marker_interiors(line: str) -> str:
    """A line with every marker interior removed, keeping the fact names."""
    return MARKER_RE.sub(lambda m: f"<!--fact:{m.group(1)}--><!--/fact-->", line)


def marker_only_rewrites(old_text: str, new_text: str) -> list[str]:
    """Findings for every change that is NOT a marker-interior rewrite.

    This is the guard that makes "it merges cleanly" a fact rather than a hope: if
    the refresh commit cannot touch anything but the interior of a fact marker,
    then the only lines it changes are lines no other branch is allowed to change
    (ADR-008), so no other branch can conflict with it.

    Pure and unit-tested. A change to the *name* inside a marker is not a
    marker-interior rewrite, so a typo'd fact name cannot ride along either.
    """
    findings: list[str] = []
    old_lines, new_lines = old_text.splitlines(), new_text.splitlines()
    if len(old_lines) != len(new_lines):
        findings.append(
            f"the line count changed ({len(old_lines)} -> {len(new_lines)}); a refresh "
            f"may only rewrite marker interiors, never add or remove lines"
        )
        return findings
    for lineno, (before, after) in enumerate(zip(old_lines, new_lines, strict=True), start=1):
        if before == after:
            continue
        if _blank_marker_interiors(before) == _blank_marker_interiors(after):
            continue
        findings.append(f"line {lineno} is not a marker rewrite: {before.strip()!r} -> {after!r}")
    return findings


def _stale_now() -> list[str]:
    """Marker values that disagree with this tree, computed cheaply.

    Cheap facts plus a live `--collect-only` test count: that catches the drift
    that actually happens (a test-adding PR, an added ADR, a new gate) in seconds.
    Coverage needs a full suite execution, so it is only resolved when the gate's
    measurement for this very commit is available; otherwise it is reported as
    unmeasured rather than guessed.
    """
    facts = collect_cheap()
    facts["test_count"] = _live_test_count()
    return stale_markers(facts)


def check() -> int:
    stale = _stale_now()
    if not stale:
        print("refresh_doc_facts: every marker matches this tree — nothing to refresh")
        return 0
    print(f"refresh_doc_facts: {len(stale)} marker value(s) are stale on the default branch:")
    for finding in stale[:20]:
        print("  -", finding)
    if len(stale) > 20:
        print(f"  … and {len(stale) - 20} more")
    print("\nRefresh them (this writes and opens the PR):")
    print("    scripts/refresh_doc_facts.py --open-pr")
    return 1


def _changed_docs() -> list[str]:
    out = _run(["git", "diff", "--name-only", "--", "docs", "*.md"]).stdout
    return [ln for ln in out.splitlines() if ln.strip()]


def _guard_changes(changed: list[str]) -> list[str]:
    """Findings for any changed document whose diff is not marker-only."""
    findings: list[str] = []
    for rel in changed:
        old = _run(["git", "show", f"HEAD:{rel}"]).stdout
        try:
            new = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except OSError as err:
            findings.append(f"{rel}: cannot read the rewritten file ({err})")
            continue
        findings += [f"{rel}: {f}" for f in marker_only_rewrites(old, new)]
    return findings


def _restore(changed: list[str]) -> None:
    if changed:
        _run(["git", "checkout", "--", *changed])


def open_pr(dry_run: bool) -> int:
    scope = resolve_fact_scope(REPO_ROOT)
    if scope.frozen and not dry_run:
        print(
            f"refresh_doc_facts: refusing to write on {scope.reason}.\n"
            "The refresh path must run on the default branch: it is the default branch's\n"
            "writer, and a branch that rewrites these lines is exactly the defect ADR-008\n"
            "exists to stop. Check out the default branch and run it there."
        )
        return 2
    dirty = _run(["git", "status", "--porcelain"]).stdout.strip()
    if dirty and not dry_run:
        print(
            "refresh_doc_facts: refusing to run with a dirty working tree — a refresh commit\n"
            "must contain nothing but marker rewrites. Commit or stash first:\n" + dirty
        )
        return 2

    facts = collect(run_tests=True)
    changed_count, updated, unknown = apply_facts(facts)
    changed = _changed_docs()
    print(f"refresh_doc_facts: rewrote {updated} marker value(s) in {changed_count} file(s)")
    if unknown:
        print(f"  {len(unknown)} marker(s) have no derivable value and were left alone")
    if not changed:
        print("refresh_doc_facts: nothing to refresh — the markers already match this tree")
        return 0

    findings = _guard_changes(changed)
    findings += check_facts(facts)
    if findings:
        _restore(changed)
        print(f"\nrefresh_doc_facts: REFUSED — {len(findings)} finding(s); all changes reverted:")
        for finding in findings[:40]:
            print("  -", finding)
        return 2
    print(f"  guarded: every changed line is a marker interior ({len(changed)} file(s))")
    for rel in changed:
        print(f"    {rel}")

    if dry_run:
        print("\n--dry-run: the diff is above/below and nothing was committed or pushed.")
        print(_run(["git", "diff", "--stat"]).stdout)
        return 0

    base = default_branch(REPO_ROOT)
    branch = f"{REFRESH_BRANCH_PREFIX}-{datetime.now(UTC).strftime('%Y%m%d')}"
    print(f"\nrefresh_doc_facts: committing on {branch} (signed by your git config)")
    for cmd in (
        ["git", "checkout", "-B", branch],
        ["git", "add", "--", *changed],
        [
            "git",
            "commit",
            "-m",
            "chore(docs): refresh documentation fact markers",
            "-m",
            "Marker-only rewrite produced by scripts/refresh_doc_facts.py: the values are\n"
            "derived from this tree, and this branch is the sole writer of those lines\n"
            "(state/DECISIONS.md ADR-008), so it merges cleanly by construction.",
        ],
    ):
        res = _run(cmd)
        if res.returncode != 0:
            print(f"refresh_doc_facts: `{' '.join(cmd)}` failed:\n{res.stderr or res.stdout}")
            return 2
    push = _run(["git", "push", "-u", "origin", branch])
    if push.returncode != 0:
        print(
            f"refresh_doc_facts: push failed:\n{push.stderr or push.stdout}\n"
            f"The commit is on {branch} locally; push it yourself and open the PR."
        )
        return 2

    body = (
        "Machine-generated by `scripts/refresh_doc_facts.py`.\n\n"
        "Every changed line is the interior of a `<!--fact:...-->` marker; nothing else is\n"
        "touched, and the script refuses to open the PR otherwise. Under ADR-008 a branch\n"
        "must never modify a fact marker line and only the default branch may, so this\n"
        "branch is the sole writer of these lines and merges cleanly by construction.\n\n"
        "The values are derived from this tree: "
        "`test_count` from `pytest --collect-only`, `coverage` from a full run with\n"
        "`--cov=app`, and the counts from the files that define them.\n"
    )
    pr = _run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            base,
            "--head",
            branch,
            "--title",
            "chore(docs): refresh documentation fact markers",
            "--body",
            body,
        ]
    )
    if pr.returncode != 0:
        existing = _run(["gh", "pr", "view", branch, "--json", "url", "--jq", ".url"])
        if existing.returncode == 0 and existing.stdout.strip():
            print(f"refresh_doc_facts: a PR for {branch} already exists: {existing.stdout.strip()}")
            return 0
        print(f"refresh_doc_facts: `gh pr create` failed:\n{pr.stderr or pr.stdout}")
        return 2
    print(f"refresh_doc_facts: {pr.stdout.strip()}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="report staleness; exit 1 if a refresh is needed",
    )
    mode.add_argument(
        "--open-pr",
        action="store_true",
        help="sync the markers, verify the change is marker-only, push and open the PR",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="with --open-pr: sync and verify in the working tree, but commit/push nothing",
    )
    args = ap.parse_args()
    if args.check:
        return check()
    return open_pr(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
