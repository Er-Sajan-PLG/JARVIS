#!/usr/bin/env python3
"""Publish GitHub Releases for JARVIS tags — the other half of release automation.

Why this exists
---------------
``githooks/pre-push`` auto-creates a SemVer tag on every push to main, and the
versioning automation works. But a tag is not a *release*: GitHub showed 21 tags
and **0 releases**, so the changelog notes, per-version download/compare links,
and the "Latest" marker never existed. ``.github/workflows/release.yml`` cannot
fill the gap because GitHub Actions is billing-blocked for this private repo
(TD-009), so the release step has to run locally, like the CI gate does.

This script closes that gap using ``gh`` rather than the REST API: the CI token
in ``.ci-bridge.env`` is fine-grained and lacks ``contents:write`` (POST
/releases → HTTP 403), while the ``gh`` CLI holds a classic token with ``repo``
scope, which can create releases.

Usage
-----
  scripts/publish_release.py                 # publish a release for the current tag
  scripts/publish_release.py --tag v3.1.2    # publish for a specific tag
  scripts/publish_release.py --backfill      # publish every tag that has no release
  scripts/publish_release.py --dry-run       # show what would be published

Exit codes
----------
  0  published (or nothing needed publishing)
  1  a real failure (gh missing/unauthenticated, API refused)

The script is idempotent: an existing release for a tag is left untouched.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")


def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    res = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def gh_available() -> bool:
    rc, _, _ = _run(["gh", "--version"], timeout=30)
    return rc == 0


def gh_authenticated() -> bool:
    rc, _, _ = _run(["gh", "auth", "status"], timeout=30)
    return rc == 0


def local_tags() -> list[str]:
    rc, out, _ = _run(["git", "tag", "--sort=creatordate"])
    if rc != 0:
        return []
    return [t for t in out.splitlines() if TAG_RE.match(t.strip())]


def released_tags() -> set[str]:
    rc, out, _ = _run(["gh", "release", "list", "--limit", "200"])
    if rc != 0:
        return set()
    tags: set[str] = set()
    for line in out.splitlines():
        # gh release list columns are tab-separated: title, type, tag, date
        parts = [p for p in line.split("\t") if p.strip()]
        for part in parts:
            if TAG_RE.match(part.strip()):
                tags.add(part.strip())
    return tags


def current_tag() -> str:
    rc, out, _ = _run(["git", "describe", "--tags", "--abbrev=0"])
    return out if rc == 0 else ""


def commits_between(prev: str | None, tag: str) -> list[str]:
    """Conventional-commit subjects between prev (exclusive) and tag (inclusive)."""
    rc, out, _ = _run(["git", "log", "--pretty=format:%s", "--no-merges"])
    if rc != 0:
        return []
    return [line for line in out.splitlines() if line.strip()]


def release_notes(tag: str) -> str:
    """Build notes from the commits that make up this release."""
    tags = local_tags()
    prev = None
    if tag in tags:
        idx = tags.index(tag)
        prev = tags[idx - 1] if idx > 0 else None

    rng = f"{prev}..{tag}" if prev else tag
    cmd = ["git", "log", "--pretty=format:%s", "--no-merges", rng]
    if prev:
        rc, out, _ = _run(cmd)
    else:
        rc, out, _ = _run(["git", "log", "--pretty=format:%s", "--no-merges", tag])
    subjects = out.splitlines() if rc == 0 else []

    buckets: dict[str, list[str]] = {
        "Features": [],
        "Fixes": [],
        "Performance": [],
        "Documentation": [],
        "Other": [],
    }
    for subject in subjects:
        s = subject.strip()
        if s.startswith("feat"):
            buckets["Features"].append(s)
        elif s.startswith("fix"):
            buckets["Fixes"].append(s)
        elif s.startswith("perf"):
            buckets["Performance"].append(s)
        elif s.startswith("docs"):
            buckets["Documentation"].append(s)
        else:
            buckets["Other"].append(s)

    lines = [f"Release {tag}", ""]
    if prev:
        lines.append(f"Changes since {prev}:")
        lines.append("")
    for heading, items in buckets.items():
        if not items:
            continue
        lines.append(f"### {heading}")
        for item in items[:40]:
            lines.append(f"- {item}")
        lines.append("")
    if len(lines) <= 3:
        lines.append("No conventional commits recorded for this release.")
    return "\n".join(lines).strip()


def publish(tag: str, notes: str, dry: bool) -> int:
    if dry:
        print(f"[dry-run] would create release {tag}")
        return 0
    rc, out, err = _run(
        ["gh", "release", "create", tag, "--title", tag, "--notes", notes],
        timeout=300,
    )
    if rc == 0:
        print(f"✅ published release {tag}")
        if out:
            print(f"   {out}")
        return 0
    print(f"❌ failed to publish {tag}: {(err or out)[:400]}", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="publish a release for this tag only")
    parser.add_argument(
        "--backfill", action="store_true", help="publish every tag missing a release"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not gh_available():
        print("error: gh CLI is not installed — cannot publish releases", file=sys.stderr)
        return 1
    if not gh_authenticated():
        print(
            "error: gh is not authenticated. Run `gh auth login`.\n"
            "Note: the fine-grained CI token in .ci-bridge.env cannot create releases "
            "(needs contents:write); gh's classic repo-scoped token can.",
            file=sys.stderr,
        )
        return 1

    have = released_tags()

    if args.tag:
        targets = [args.tag]
    elif args.backfill:
        targets = [t for t in local_tags() if t not in have]
    else:
        tag = current_tag()
        if not tag:
            print("error: no tag at HEAD (or no vA.B.C tags at all)", file=sys.stderr)
            return 1
        if tag in have:
            print(f"release for {tag} already exists — nothing to do")
            return 0
        targets = [tag]

    if not targets:
        print("all tags already have releases — nothing to do")
        return 0

    print(f"publishing {len(targets)} release(s): {', '.join(targets)}")
    failed = 0
    for tag in targets:
        if publish(tag, release_notes(tag), args.dry_run) != 0:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
