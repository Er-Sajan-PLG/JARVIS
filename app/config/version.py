"""
JARVIS — automatic versioning.

The single source of truth for the version is the set of git tags that follow
the ``vA.B.C`` scheme, where:

    A = major      (breaking / big architectural change)
    B = feature    (new capability, backwards compatible)
    C = patch      (bug fixes / small changes)

This module *derives* the running version from git at import time instead of
hardcoding it, so the version always reflects the true development history:

* HEAD exactly on a clean ``vA.B.C`` tag            -> ``v2.4.2``   (release)
* HEAD ahead of the latest tag (N commits)          -> ``v2.4.2+dev.3``
* Working tree dirty (even on a tag)                -> ``...dirty``

Fallbacks (no ``.git``, no tags, or git missing):
    1. ``JARVIS_VERSION`` environment variable.
    2. ``_FALLBACK_VERSION`` below (last known release) — only used when git
       is entirely unavailable (e.g. a built artifact without a repo).
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

# Last known release — used ONLY when git is unavailable. When git is present
# this constant is ignored in favour of the actual tag history.
_FALLBACK_VERSION = "v3.0.0"

# Canonical release tag: vA.B.C
_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

# Output of `git describe --tags --long`: "<tag>-<commits>-g<hash>"
_DESCRIBE_RE = re.compile(r"^(v[\d.]+)-(\d+)-g([0-9a-f]+)$")


def _run_git(*args: str) -> str | None:
    """Run a git command from the repo; return stripped stdout or None on failure."""
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _is_dirty() -> bool:
    return bool(_run_git("status", "--porcelain"))


@dataclass(frozen=True)
class VersionInfo:
    major: int
    minor: int
    patch: int
    base_tag: str        # latest vA.B.C tag this version is based on
    commits_since: int   # commits since base_tag
    git_hash: str        # short commit hash ("" when unknown)
    dirty: bool          # working tree has uncommitted changes
    release: bool        # exactly on a clean tag
    source: str          # "git" | "env" | "fallback"

    @property
    def as_tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __str__(self) -> str:
        if self.release:
            # Exactly on a clean tagged commit.
            return self.base_tag
        if self.commits_since == 0:
            # On the tag commit but the tree is dirty.
            return f"{self.base_tag}.dirty"
        # Ahead of the latest release tag.
        suffix = f"+dev.{self.commits_since}"
        if self.dirty:
            suffix += ".dirty"
        return f"{self.base_tag}{suffix}"


def get_version_info() -> VersionInfo:
    """Compute the version from git tags, with env/fallback fallbacks."""

    # 1) Derive from the nearest vA.B.C tag via `git describe`.
    describe = _run_git(
        "describe", "--tags", "--long",
        "--match", "v[0-9]*.[0-9]*.[0-9]*",
    )
    if describe:
        m = _DESCRIBE_RE.match(describe)
        if m and (tm := _TAG_RE.match(m.group(1))):
            ahead = int(m.group(2))
            return VersionInfo(
                major=int(tm.group(1)),
                minor=int(tm.group(2)),
                patch=int(tm.group(3)),
                base_tag=m.group(1),
                commits_since=ahead,
                git_hash=m.group(3),
                dirty=_is_dirty(),
                release=(ahead == 0 and not _is_dirty()),
                source="git",
            )

    # 2) Inside a git repo but no vA.B.C tag yet.
    if _run_git("rev-parse", "--is-inside-work-tree") == "true":
        head = _run_git("rev-parse", "--short", "HEAD") or "unknown"
        return VersionInfo(
            0, 0, 0, "v0.0.0", 0, head, _is_dirty(), False, "git",
        )

    # 3) Explicit environment override.
    env = (os.environ.get("JARVIS_VERSION") or "").strip()
    if env and (tm := _TAG_RE.match(env)):
        return VersionInfo(
            int(tm.group(1)), int(tm.group(2)), int(tm.group(3)),
            env, 0, "", False, True, "env",
        )

    # 4) Last-resort fallback constant.
    tm = _TAG_RE.match(_FALLBACK_VERSION)
    return VersionInfo(
        int(tm.group(1)), int(tm.group(2)), int(tm.group(3)),
        _FALLBACK_VERSION, 0, "", False, False, "fallback",
    )


# --- Public API -----------------------------------------------------------
_VERSION_INFO = get_version_info()

VERSION: str = str(_VERSION_INFO)

# Convenience named accessors
MAJOR = _VERSION_INFO.major
MINOR = _VERSION_INFO.minor
PATCH = _VERSION_INFO.patch
BASE_TAG = _VERSION_INFO.base_tag
COMMITS_SINCE_TAG = _VERSION_INFO.commits_since
GIT_HASH = _VERSION_INFO.git_hash
DIRTY = _VERSION_INFO.dirty
IS_RELEASE = _VERSION_INFO.release
VERSION_SOURCE = _VERSION_INFO.source

__all__ = [
    "VERSION", "get_version_info", "VersionInfo",
    "MAJOR", "MINOR", "PATCH", "BASE_TAG", "COMMITS_SINCE_TAG",
    "GIT_HASH", "DIRTY", "IS_RELEASE", "VERSION_SOURCE",
]
