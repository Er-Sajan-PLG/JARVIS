#!/usr/bin/env python3
"""Configure the GitHub ruleset that protects `main` for JARVIS.

Makes the enforcement real. Until 2026-10-01 this repository was private on a Free
plan, so branch protection returned **HTTP 403** ("Upgrade to GitHub Pro or make
this repository public") and every rule below existed only as convention --
RISK-011 and RISK-012 in docs/ACCEPTED_RISKS.md. Now that the repository is
public, GitHub will enforce them, and this script is what installs them.

The previous version of this file was a trap. It required six status-check
contexts from `.github/workflows/ci.yml` -- "Lint & Typecheck", "Tests", "Security
Scan", "Build", "Conventional Commits", "Virtual Board Governance". That workflow
had been disabled since 2026-09-10 and had **never run**, so none of those checks
ever reported. A required check that never reports does not pass, and the branch
would have been permanently unmergeable. The workflow has since been deleted and
replaced by `ci-gate.yml`, which runs `scripts/ci_gate.py`.

Usage:
    gh auth refresh -s admin:repo_hook   # if the token lacks scope
    .venv/bin/python scripts/setup_branch_protection.py --dry-run
    .venv/bin/python scripts/setup_branch_protection.py

Requires: the `gh` CLI, authenticated with admin rights on the repository.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

REPO = "Er-Sajan-PLG/JARVIS"
BRANCH = "main"

# The workflow's job name, which is the context GitHub reports. There is exactly
# one: one gate definition, one required check. Requiring anything else would
# reintroduce the "two definitions of green" problem this replaced.
REQUIRED_CHECK = "ci-gate"

RULESET_NAME = "protect-main"


def gh(*args: str, stdin: dict | None = None) -> tuple[int, str, str]:
    cmd = ["gh", "api", "--method", args[0], args[1], *args[2:]]
    result = subprocess.run(
        cmd,
        input=json.dumps(stdin) if stdin is not None else None,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def build_ruleset() -> dict:
    """The ruleset payload.

    Notes on two deliberate choices:

    * ``required_approving_review_count`` is 0. GitHub forbids approving your own
      pull request, so on a solo repository any higher number makes `main`
      unmergeable -- the same trap the old script set with its status checks.
      The review requirement is structural (a PR must exist); the CI check is what
      provides the actual gate.
    * ``strict_required_status_checks_policy`` is True, so a branch must be up to
      date with `main` before merging. Without it a green run from before a
      conflicting merge can be reused, and two PRs can each pass while their
      combination does not.
    """
    return {
        "name": RULESET_NAME,
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "required_linear_history"},
            {"type": "required_signatures"},
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 0,
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_review_thread_resolution": True,
                    "allowed_merge_methods": ["squash", "rebase"],
                },
            },
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "do_not_enforce_on_create": False,
                    "required_status_checks": [{"context": REQUIRED_CHECK}],
                },
            },
        ],
    }


def existing_ruleset_id() -> int | None:
    code, out, _ = gh("GET", f"repos/{REPO}/rulesets")
    if code != 0:
        return None
    try:
        for rs in json.loads(out):
            if rs.get("name") == RULESET_NAME:
                return rs.get("id")
    except json.JSONDecodeError:
        return None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print the payload, change nothing")
    args = parser.parse_args()

    payload = build_ruleset()

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    status = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if status.returncode != 0:
        print("Error: gh CLI is not authenticated. Run 'gh auth login'.", file=sys.stderr)
        return 1

    print(f"Configuring ruleset '{RULESET_NAME}' for {REPO}@{BRANCH}")
    print(f"  required check : {REQUIRED_CHECK}")

    rid = existing_ruleset_id()
    if rid is not None:
        print(f"  existing ruleset id={rid}, updating")
        code, out, err = gh("PUT", f"repos/{REPO}/rulesets/{rid}", stdin=payload)
    else:
        print("  no existing ruleset, creating")
        code, out, err = gh("POST", f"repos/{REPO}/rulesets", stdin=payload)

    if code != 0:
        print(f"FAILED: {err.strip()}", file=sys.stderr)
        return 1

    print("  OK")
    try:
        body = json.loads(out)
    except json.JSONDecodeError:
        return 0

    rules = [r.get("type") for r in body.get("rules", [])]
    print(f"  enforcement : {body.get('enforcement')}")
    print(f"  rules       : {', '.join(rules)}")
    for rule in body.get("rules", []):
        if rule.get("type") == "required_status_checks":
            checks = rule.get("parameters", {}).get("required_status_checks", [])
            print(f"  checks      : {[c.get('context') for c in checks]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
