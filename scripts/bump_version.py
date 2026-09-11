#!/usr/bin/env python3
"""Version bump script for JARVIS.

Usage: python scripts/bump_version.py [patch|minor|major]
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"


def get_current_version() -> str:
    """Get current version from pyproject.toml."""
    content = PYPROJECT.read_text()
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    if not match:
        raise ValueError("Version not found in pyproject.toml")
    return match.group(1)


def bump_version(version: str, bump_type: str) -> str:
    """Bump version according to semver."""
    major, minor, patch = map(int, version.split("."))

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}. Use patch|minor|major")

    return f"{major}.{minor}.{patch}"


def update_pyproject(new_version: str) -> None:
    """Update version in pyproject.toml."""
    content = PYPROJECT.read_text()
    new_content = re.sub(r'version\s*=\s*"[^"]+"', f'version = "{new_version}"', content)
    PYPROJECT.write_text(new_content)


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run command and return result (text mode)."""
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def install_hooks() -> None:
    """Point git at the tracked githooks/ dir (version guard + pre-push reminder)."""
    subprocess.run(["git", "config", "core.hooksPath", "githooks"], check=True)
    print("✅ core.hooksPath set to 'githooks' (pre-commit + pre-push hooks active).")


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "install-hooks":
        install_hooks()
        return

    if len(sys.argv) != 2 or sys.argv[1] not in ("patch", "minor", "major"):
        print("Usage: python scripts/bump_version.py [patch|minor|major|install-hooks]")
        sys.exit(1)

    bump_type = sys.argv[1]

    # Get current version
    current = get_current_version()
    print(f"Current version: {current}")

    # Calculate new version
    new_version = bump_version(current, bump_type)
    print(f"New version: {new_version}")

    # Confirm
    response = input(f"Bump {bump_type}: {current} → {new_version}? (y/N): ")
    if response.lower() != "y":
        print("Aborted.")
        sys.exit(0)

    # Update pyproject.toml
    update_pyproject(new_version)
    print("Updated pyproject.toml")

    # Git operations. The TAG is the source of truth (see docs/VERSIONING.md and
    # app/config/version.py); bumping pyproject.toml is a courtesy so the
    # metadata stays close, never the authority.
    print("Running git operations...")
    run_cmd(["git", "add", "pyproject.toml"])
    run_cmd(["git", "commit", "-m", f"chore(release): bump version to {new_version}"])
    try:
        run_cmd(["git", "tag", "-s", f"v{new_version}", "-m", f"Release v{new_version}"])
    except Exception:
        print("⚠️  No GPG key found — creating an unsigned (annotated) tag instead.")
        run_cmd(["git", "tag", "-a", f"v{new_version}", "-m", f"Release v{new_version}"])
    run_cmd(["git", "push", "origin", "main"])
    run_cmd(["git", "push", "origin", f"v{new_version}"])

    print(f"\n✅ Version bumped to v{new_version}")
    print("Release workflow will trigger on tag push.")


if __name__ == "__main__":
    main()
