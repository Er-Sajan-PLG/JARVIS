#!/usr/bin/env python3
"""Configure GitHub branch protection for JARVIS repository.

This script sets up branch protection rules on the main branch:
- Required status checks from CI workflow
- No force pushes
- Linear history (squash merge)
- Required PR reviews (can be 0 for solo repo)
- Dismiss stale approvals
- Require branches to be up to date before merging

Run with: python scripts/setup_branch_protection.py
Requires: GITHUB_TOKEN environment variable with repo admin permissions
"""

import json
import os
import subprocess
import sys

REPO_OWNER = "Er-Sajan-PLG"
REPO_NAME = "JARVIS"
BRANCH = "main"

REQUIRED_CHECKS = [
    "Lint & Typecheck",
    "Tests",
    "Security Scan",
    "Build",
    "Conventional Commits",
    "Virtual Board Governance",
]


def run_gh_api(method: str, endpoint: str, data: dict = None) -> dict:
    """Run gh api command and return parsed JSON."""
    cmd = ["gh", "api", "--method", method, endpoint]
    if data:
        cmd.extend(["--input", "-"])
        result = subprocess.run(cmd, input=json.dumps(data), capture_output=True, text=True)
    else:
        result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return {}

    try:
        return json.loads(result.stdout) if result.stdout else {}
    except json.JSONDecodeError:
        return {}


def get_current_protection() -> dict:
    """Get current branch protection rules."""
    return run_gh_api("GET", f"repos/{REPO_OWNER}/{REPO_NAME}/branches/{BRANCH}/protection")


def create_protection_payload() -> dict:
    """Create branch protection configuration payload."""
    return {
        "required_status_checks": {"strict": True, "contexts": REQUIRED_CHECKS},
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "required_approving_review_count": 0,
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": False,
            "require_last_push_approval": False,
        },
        "restrictions": {},
        "required_linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "required_conversation_resolution": True,
        "lock_branch": False,
        "allow_fork_syncing": True,
    }


def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable required")
        sys.exit(1)

    # Check if gh is authenticated
    result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if result.returncode != 0:
        print("Error: gh CLI not authenticated. Run 'gh auth login'")
        sys.exit(1)

    print(f"Configuring branch protection for {REPO_OWNER}/{REPO_NAME}@{BRANCH}")

    # Get current protection
    current = get_current_protection()
    if current:
        print("Current protection exists, updating...")
    else:
        print("No existing protection, creating new...")

    payload = create_protection_payload()
    print(f"Required checks: {REQUIRED_CHECKS}")

    result = run_gh_api(
        "PUT", f"repos/{REPO_OWNER}/{REPO_NAME}/branches/{BRANCH}/protection", payload
    )
    if result:
        print("✅ Branch protection configured successfully!")
        print(f"Required checks: {result.get('required_status_checks', {}).get('contexts', [])}")
        print(f"Linear history: {result.get('required_linear_history')}")
        print(f"Force pushes allowed: {result.get('allow_force_pushes')}")
        print(f"Admin enforcement: {result.get('enforce_admins')}")
    else:
        print("❌ Failed to configure branch protection")
        sys.exit(1)


if __name__ == "__main__":
    main()
