"""Deterministic SemVer bump from conventional commits since the last release tag.

This is the piece of the "automatic versioning" that was never built. The
arrangement on this repo is:

* ``app/config/version.py`` DERIVES the version from git tags at import time.
* ``scripts/bump_version.py`` BUMPs a version interactively, by hand.
* ``githooks/pre-push`` REMINDED the human to bump, then ``exit 0``.

Nothing ever CREATED a tag on its own, so the version silently drifted as
``v3.0.1+dev.148``. This module closes that gap: it computes the next ``vA.B.C``
from the conventional commit types since the latest release tag, then (when
invoked as ``--apply``) creates the annotated tag and bumps ``pyproject.toml``.

Bump rules (semver + conventional commits):
    breaking / BREAKING CHANGE   -> MAJOR
    feat                         -> MINOR
    anything else                -> PATCH

Safety: if there are NO conventional commits since the latest tag, it refuses to
bump (returns nothing) rather than inventing a patch tag. This keeps a tag cut
from being a no-op marker for work that never happened.

Determinism / stdlib-only: the module uses only ``subprocess`` + ``re`` so the
pre-push hook can run it with no third-party dependency and no network.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

# Conventional-commit prefix -> bump level. ``major`` beats ``minor`` beats
# ``patch`` regardless of commit order.
_BUMP_BY_TYPE = {
    "breaking": "major",
}
# ``feat`` and ``fix`` are the only types that imply a bump; everything else is
# a no-change-for-versioning commit (docs/chore/test/refactor/ci/build/style/perf
# are deliberately NOT a bump on their own, matching commitlint's version-bump map).
_MINOR_TYPES = {"feat"}


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or REPO_ROOT)
    return proc.stdout


def latest_tag() -> str:
    """Return the newest vA.B.C tag reachable from HEAD, or "" if none."""
    out = _run(["git", "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*.[0-9]*.[0-9]*"])
    tag = out.strip()
    return tag if _TAG_RE.match(tag) else ""


def _commit_subjects_since(tag: str) -> list[str]:
    if tag:
        out = _run(["git", "log", f"{tag}..HEAD", "--pretty=format:%s"])
    else:
        out = _run(["git", "log", "--pretty=format:%s"])
    return [line for line in out.splitlines() if line.strip()]


def _classify(subject: str) -> str:
    """Return the bump level a single commit subject implies ('major'|'minor'|'patch')."""
    if "BREAKING CHANGE" in subject or subject.lower().startswith("breaking"):
        return "major"
    m = re.match(r"^(feat|fix)\b", subject, re.IGNORECASE)
    if m:
        return "minor" if m.group(1).lower() == "feat" else "patch"
    return "patch"


def compute_bump() -> tuple[str, str, int] | None:
    """Return (next_tag, bump_level, commits_considered) or None if nothing to bump."""
    tag = latest_tag()
    subjects = _commit_subjects_since(tag)

    if not subjects:
        return None

    level = "patch"
    for s in subjects:
        lvl = _classify(s)
        if lvl == "major":
            level = "major"
            break
        if lvl == "minor" and level != "major":
            level = "minor"

    tag_parts = _TAG_RE.match(tag) if tag else None
    major, minor, patch = (int(x) for x in tag_parts.groups()) if tag_parts else (0, 0, 0)

    if level == "major":
        major, minor, patch = major + 1, 0, 0
    elif level == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1

    return f"v{major}.{minor}.{patch}", level, len(subjects)


def bump_pyproject(next_tag: str) -> None:
    """Update the ``project.version`` metadata (courtesy, not the authority)."""
    p = REPO_ROOT / "pyproject.toml"
    text = p.read_text()
    new = re.sub(r'version\s*=\s*"[^"]+"', f'version = "{next_tag.lstrip("v")}"', text)
    p.write_text(new)


def main(argv: list[str]) -> int:
    apply_tag = "--apply" in argv
    tag_only = "--tag-only" in argv
    result = compute_bump()

    if result is None:
        print("No conventional commits since the latest tag — nothing to bump.")
        return 0

    next_tag, level, n = result
    print(f"next version {next_tag} ({level}, {n} commit(s) since {latest_tag() or 'start'})")

    if not apply_tag:
        # Dry-run (the default): report only, touch nothing.
        return 0

    if tag_only:
        # Tag HEAD directly without committing anything (pre-push hook path):
        # the commits being tagged are ALREADY committed and about to be pushed,
        # so we must not mint a new commit here or the tag would dangle on an
        # unpushed commit.
        if Path(REPO_ROOT / ".git").exists():
            subprocess.run(
                ["git", "tag", "-a", next_tag, "-m", f"Release {next_tag}"],
                cwd=REPO_ROOT,
                check=True,
            )
            print(f"✅ created tag {next_tag} at HEAD (no commit created)")
            return 0
        print("error: --tag-only requires a git repo")
        return 1

    bump_pyproject(next_tag)
    subprocess.run(["git", "add", "pyproject.toml"], cwd=REPO_ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"chore(release): bump version to {next_tag}"],
        cwd=REPO_ROOT,
        check=True,
    )
    # Annotated tag (unsigned — no GPG key on this box, RISK-011).
    subprocess.run(
        ["git", "tag", "-a", next_tag, "-m", f"Release {next_tag}"],
        cwd=REPO_ROOT,
        check=True,
    )
    print(f"✅ created tag {next_tag} and bumped pyproject.toml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
