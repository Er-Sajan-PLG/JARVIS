#!/usr/bin/env python3
"""Pre-commit governance check for JARVIS.

Runs all governance checks that must pass before commit.
This is the single source of truth for compliance.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_check(name: str, cmd: list[str]) -> tuple[bool, str]:
    """Run a check and return (passed, output)."""
    print(f"\n🔍 {name}...")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    if result.returncode == 0:
        print(f"  ✅ {name} passed")
        return True, result.stdout
    else:
        print(f"  ❌ {name} failed")
        print(f"  {result.stdout}")
        print(f"  {result.stderr}")
        return False, result.stderr


def main():
    """Run all pre-commit governance checks."""
    print("=" * 60)
    print("JARVIS PRE-COMMIT GOVERNANCE CHECKS")
    print("=" * 60)

    checks = [
        ("Ruff Lint", [".venv/bin/ruff", "check", "app/", "tests/"]),
        ("Ruff Format", [".venv/bin/ruff", "format", "--check", "app/", "tests/"]),
        ("Mypy Strict", [".venv/bin/mypy", "--strict", "app/"]),
        ("Pytest Quick", [".venv/bin/pytest", "tests/", "-q"]),
        ("Governance Board", [".venv/bin/python", "scripts/board/review.py"]),
    ]

    all_passed = True
    for name, cmd in checks:
        passed, _ = run_check(name, cmd)
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL GOVERNANCE CHECKS PASSED")
        print("=" * 60)
        return 0
    else:
        print("💥 SOME GOVERNANCE CHECKS FAILED")
        print("=" * 60)
        print("\nFix all failures before committing.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
