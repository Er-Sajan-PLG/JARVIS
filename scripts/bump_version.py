#!/usr/bin/env python3
"""
JARVIS version bumper — the bridge between git tags and the automatic version.

The version system is ``vA.B.C``  (A=major, B=feature, C=patch). The true
development history lives in the git tags, and ``app/config/version.py``
derives the running version from them. This script *bases a new version off the
latest existing tag* and records it as an annotated git tag so the automatic
version picks it up.

Commands
--------
    python scripts/bump_version.py bump patch
        Bump the patch component of the latest tag and create an annotated tag.
        (v2.4.2 -> v2.4.3)

    python scripts/bump_version.py bump minor
        Bump the feature component, reset patch to 0. (v2.4.2 -> v2.5.0)

    python scripts/bump_version.py bump major
        Bump the major component, reset feature+patch to 0. (v2.4.2 -> v3.0.0)

    Release notes ("points") can be supplied three ways and are stored in the
    annotated tag (view later with: git show vX.Y.Z):
      - repeated -m / --message flags :  bump minor -m "Added X" -m "Fixed Y"
          (each -m becomes a bullet point)
      - a notes file                  :  bump minor --notes-file NOTES.md
          (used verbatim, so you can write full Markdown / bullets yourself)
      - interactively                 :  bump minor   (prompts for lines; blank ends;
          each line becomes a bullet point)
    The tag title is always "JARVIS vX.Y.Z"; your points follow it as the body.
    Use --no-bullets to keep -m / interactive notes verbatim.

    python scripts/bump_version.py show
        Print the version that git currently derives (with diagnostics).

    python scripts/bump_version.py current-tag
        Print the latest vA.B.C tag.

    python scripts/bump_version.py install-hooks
        Install the git hooks from githooks/ (sets core.hooksPath).

    python scripts/bump_version.py sync
        Normalise every version mention found in the source tree to the
        canonical ``vA.B.C`` form. Typos such as ``v.2.4.2`` or ``v 2 4 2`` are
        rewritten to ``v2.4.2``. No numbers are changed (renumbering only
        happens on `bump`). Use --dry-run to preview.

Automatic source sync
---------------------
    `bump` automatically rewrites version mentions across the codebase (every
    tracked source file except docs/, markdown, vendored/cache dirs and a few
    tooling/config files — see SOURCE_EXCLUDE_* near the top of this file). On a
    bump, every canonical mention equal to the old release is advanced to the
    new one, and any typo'd mention is first normalised so it matches and is
    bumped too. Use --no-sync to skip this, or --dry-run to preview every change.

Useful flags for `bump`:
    --at REF            tag a specific commit/branch (default HEAD)
    -m, --message TXT   release note line (repeatable); each becomes a bullet point
    --notes-file PATH   read release notes from this file (used as the tag body)
    --no-bullets        keep -m / interactive notes verbatim (no bullet prefix)
    --sync-package      also write the version into package.json
    --dry-run           show what would happen (including the message) without tagging
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

# --- Source-wide version synchronisation ----------------------------------
# These rules drive the automatic rewriting of version mentions across the
# codebase whenever a bump happens (see ``sync_source_versions``). The idea is:
# every place that *mentions* the project version (e.g. ``v2.4.2``) — including
# typos such as ``v.2.4.2``, ``v 2 4 2`` or ``v2-4-2`` — is normalised to the
# canonical ``vA.B.C`` form and, on a bump, advanced to the new version.
# Historical version references that do NOT equal the current release are left
# untouched (they are never renumbered).

# Directories that are never walked for version mentions.
SOURCE_EXCLUDE_DIRS = {
    ".git", "docs", "node_modules", "__pycache__", "data",
    ".venv", "venv", "env", "dist", "build", ".mypy_cache", ".pytest_cache",
}

# Individual files (relative to the repo root) that must never be rewritten by
# the generic scan. ``package.json`` / ``package-lock.json`` are handled by the
# dedicated package sync, ``config.yaml`` is agent-protected, and this script
# never rewrites itself.
SOURCE_EXCLUDE_FILES = {
    "package.json",
    "package-lock.json",
    "config.yaml",
    "scripts/bump_version.py",
}

# File extensions that are scanned for version mentions.
SOURCE_INCLUDE_EXT = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".txt", ".conf",
}

# Matches a version-like token: a ``v`` (case-insensitive) followed by three
# numbers with lenient separators, so typos such as ``v.2.4.2``, ``v 2 4 2`` or
# ``v2-4-2`` are captured and normalised to ``vA.B.C``.
VERSION_TOKEN_RE = re.compile(
    r"(?i)\bv[.\s]*(?P<major>\d+)(?:[.\s-]*)(?P<minor>\d+)(?:[.\s-]*)(?P<patch>\d+)\b"
)


def _git(*args: str, check: bool = True, capture: bool = True) -> str:
    res = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=capture,
        text=True,
    )
    if check and res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout.strip() if capture else ""


def latest_version_tag() -> tuple[int, int, int] | None:
    """Return the highest (major, minor, patch) among vA.B.C tags, else None."""
    out = _git("tag", "--list", "v[0-9]*.[0-9]*.[0-9]*", check=False)
    tags: list[tuple[int, int, int]] = []
    for line in (out or "").splitlines():
        m = TAG_RE.match(line.strip())
        if m:
            tags.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return max(tags) if tags else None


def bump(base: tuple[int, int, int] | None, part: str) -> tuple[int, int, int]:
    a, b, c = base or (0, 0, 0)
    if part == "major":
        return (a + 1, 0, 0)
    if part == "minor":
        return (a, b + 1, 0)
    return (a, b, c + 1)


def fmt(t: tuple[int, int, int]) -> str:
    return f"v{t[0]}.{t[1]}.{t[2]}"


def tag_exists(tag: str) -> bool:
    return _git("rev-parse", tag, check=False) != ""


def create_tag(tag: str, ref: str, message: str) -> None:
    if tag_exists(tag):
        raise SystemExit(f"❌ Tag {tag} already exists.")
    _git("tag", "-a", tag, "-m", message, ref)
    print(f"✅ Created annotated tag {tag} -> {ref}")


def sync_package_json(tag: str) -> None:
    for pj_rel in ["package.json", "frontend/package.json"]:
        pj = os.path.join(REPO_ROOT, pj_rel)
        if not os.path.exists(pj):
            continue
        with open(pj) as f:
            data = json.load(f)
        data["version"] = tag.lstrip("v")
        with open(pj, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        print(f"📦 Updated {pj_rel} version -> {data['version']}")



def iter_source_files():
    """Yield absolute paths of source files to scan for version mentions.

    Walks the repo, skipping excluded directories (docs, vendored, caches,
    hidden dirs) and files, and only yielding files with a scannable extension.
    """
    for root, dirs, files in os.walk(REPO_ROOT):
        # Prune excluded / hidden directories in place so os.walk skips them.
        dirs[:] = [
            d for d in dirs
            if d not in SOURCE_EXCLUDE_DIRS and not d.startswith(".")
        ]
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), REPO_ROOT)
            if rel in SOURCE_EXCLUDE_FILES or name in SOURCE_EXCLUDE_FILES:
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in SOURCE_INCLUDE_EXT:
                continue
            yield os.path.join(root, name)


def rewrite_versions(text: str, old: str | None, new: str | None):
    """Rewrite version tokens in *text*.

    * If *old* and *new* are given, every token whose canonical form equals
      *old* is replaced with *new* (this is what advances the version on a
      bump).
    * Every token that is not already in canonical ``vA.B.C`` form (e.g. a typo
      such as ``v.2.4.2``) is normalised to canonical form regardless.

    Returns ``(new_text, [(original, replacement), ...])``.
    """
    changes: list[tuple[str, str]] = []

    def _repl(m: re.Match) -> str:
        canon = f"v{int(m.group('major'))}.{int(m.group('minor'))}.{int(m.group('patch'))}"
        original = m.group(0)
        if old is not None and canon == old:
            changes.append((original, new))
            return new
        if original != canon:
            changes.append((original, canon))
            return canon
        return original

    new_text = VERSION_TOKEN_RE.sub(_repl, text)
    return new_text, changes


def sync_source_versions(old: str | None, new: str | None, *, dry_run: bool = False) -> int:
    """Normalise / bump version mentions across all scanned source files.

    *old* / *new* are canonical version strings (e.g. ``"v2.4.2"``). Pass
    ``None`` for both to only normalise typo'd formats without renumbering.
    With *dry_run* nothing is written; changes are only reported.

    Returns the number of individual replacements made.
    """
    total_files = 0
    total_changes = 0
    for path in iter_source_files():
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except (UnicodeDecodeError, OSError):
            continue
        new_text, changes = rewrite_versions(text, old, new)
        if not changes:
            continue
        total_files += 1
        rel = os.path.relpath(path, REPO_ROOT)
        for original, replacement in changes:
            total_changes += 1
            print(f"  {rel}: {original!r} -> {replacement!r}")
        if not dry_run:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_text)
    if total_changes == 0:
        print("🔸 No version mentions to update.")
    else:
        verb = "Would update" if dry_run else "Updated"
        print(f"🔸 {verb} {total_changes} version mention(s) across {total_files} file(s).")
    return total_changes


def _prompt_notes() -> str:
    """Interactively collect multi-line release notes (blank line ends)."""
    print("Enter release notes (one line each; blank line to finish):")
    lines: list[str] = []
    while True:
        try:
            line = input("  > ")
        except EOFError:
            break
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines)


def _build_message(tag: str, args: argparse.Namespace) -> str:
    """Build the annotated tag message from supplied or interactive release notes.

    Notes supplied via repeated -m flags or the interactive prompt are turned
    into bullet points (one "point" per line) unless --no-bullets is given.
    A --notes-file is used verbatim so you can supply any Markdown you like.
    """
    source, raw = "", ""
    if args.notes_file:
        with open(args.notes_file) as f:
            raw = f.read().strip()
        source = "file"
    elif args.message:
        raw = "\n".join(args.message)
        source = "flags"
    elif sys.stdin.isatty() and not args.dry_run:
        raw = _prompt_notes()
        source = "prompt"

    if raw and source != "file" and not args.no_bullets:
        body = "\n".join(
            f"- {ln}" if not ln.strip().startswith(("-", "*", "•", "+"))
            else ln
            for ln in raw.splitlines() if ln.strip()
        )
    else:
        body = raw

    return f"JARVIS {tag}\n\n{body}" if body else f"JARVIS {tag}"


def show_version() -> None:
    sys.path.insert(0, REPO_ROOT)
    from app.config.version import (
        VERSION, VERSION_SOURCE, BASE_TAG, COMMITS_SINCE_TAG, DIRTY,
    )
    print(
        f"{VERSION}  (source={VERSION_SOURCE}, base={BASE_TAG}, "
        f"ahead={COMMITS_SINCE_TAG}, dirty={DIRTY})"
    )


def install_hooks() -> None:
    hooks_dir = os.path.join(REPO_ROOT, "githooks")
    if not os.path.isdir(hooks_dir):
        raise SystemExit("❌ githooks/ directory not found.")
    _git("config", "core.hooksPath", "githooks")
    for name in os.listdir(hooks_dir):
        path = os.path.join(hooks_dir, name)
        if os.path.isfile(path):
            os.chmod(path, 0o755)
    print("✅ Git hooks installed (core.hooksPath = githooks)")


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS automatic version bumper (vA.B.C).")
    sub = parser.add_subparsers(dest="cmd")

    p_bump = sub.add_parser("bump", help="Bump and tag a new version.")
    p_bump.add_argument("part", choices=["major", "minor", "patch"])
    p_bump.add_argument("--at", default="HEAD", help="Git ref to tag (default HEAD).")
    p_bump.add_argument("-m", "--message", action="append", default=None,
                        help="Release note line (repeatable). Each becomes a bullet point.")
    p_bump.add_argument("--notes-file", default=None,
                        help="Read release notes from this file (used as the tag body).")
    p_bump.add_argument("--no-bullets", action="store_true",
                        help="Keep -m / interactive notes verbatim (no bullet prefix).")
    p_bump.add_argument("--sync-package", action="store_true",
                        help="Also update package.json version.")
    p_bump.add_argument("--no-sync", action="store_true",
                        help="Do not rewrite version mentions in source files.")
    p_bump.add_argument("--dry-run", action="store_true",
                        help="Show the new version without creating a tag.")

    sub.add_parser("show", help="Print the current derived version.")
    sub.add_parser("current-tag", help="Print the latest vA.B.C tag.")
    sub.add_parser("install-hooks", help="Install git hooks from githooks/.")
    p_sync = sub.add_parser(
        "sync",
        help="Normalise version mentions to vA.B.C format (no renumbering).",
    )
    p_sync.add_argument("--dry-run", action="store_true",
                        help="Show the normalisations without writing files.")

    args = parser.parse_args()
    if args.cmd is None:
        parser.print_help()
        return

    if args.cmd == "show":
        show_version()
        return
    if args.cmd == "install-hooks":
        install_hooks()
        return
    if args.cmd == "current-tag":
        base = latest_version_tag()
        print(fmt(base) if base else "none")
        return

    if args.cmd == "sync":
        sync_source_versions(None, None, dry_run=args.dry_run)
        return

    if args.cmd == "bump":
        base = latest_version_tag()
        new = bump(base, args.part)
        tag = fmt(new)
        msg = _build_message(tag, args)
        old_canonical = fmt(base) if base else None

        if args.dry_run:
            print(f"🔸 Would bump {fmt(base) if base else 'none'} -> {tag}")
            print(f"🔸 Tag message:\n{msg}")
            if args.sync_package:
                print(f"🔸 Would set package.json version -> {tag.lstrip('v')}")
            if not args.no_sync:
                print("🔸 Source version mentions that would change:")
                sync_source_versions(old_canonical, tag, dry_run=True)
            return

        create_tag(tag, args.at, msg)
        if args.sync_package:
            sync_package_json(tag)
        if not args.no_sync:
            sync_source_versions(old_canonical, tag, dry_run=False)
        print(f"🚀 New version: {tag}")
        print(f"📝 Tag message:\n{msg}")
        return


if __name__ == "__main__":
    main()
