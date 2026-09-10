#!/usr/bin/env bash
# Commit helper for JARVIS.
#
# WHY THIS EXISTS
# --------------
# Four hooks in .pre-commit-config.yaml *rewrite* files rather than checking them:
#   ruff --fix, ruff-format, trailing-whitespace, end-of-file-fixer
# pre-commit exits non-zero whenever a hook modifies a file, so the first
# `git commit` after any edit ALWAYS aborts with "files were modified by this
# hook". The usual response — re-run `git commit` — works, but it is easy to
# mistake the abort for a real failure, and it trains people to ignore a red
# pre-commit output.
#
# This wrapper makes the two-pass behaviour explicit and automatic:
#   1. stage what the caller asked for
#   2. run pre-commit; if it fixed files, re-stage them
#   3. run pre-commit again to prove it is now clean
#   4. commit
# If the second pass still fails, the failure is real and the commit stops.
#
# Usage:  scripts/commit.sh -m "feat(scope): message"        # or
#         scripts/commit.sh -F /path/to/message-file
# All arguments are passed through to `git commit` unchanged.

set -euo pipefail
cd "$(dirname "$0")/.."

if [ "$#" -eq 0 ]; then
    echo "usage: scripts/commit.sh -m \"message\" | -F <file>" >&2
    exit 2
fi

# Pass 1 -- let the auto-fixers do their work. A non-zero exit here is EXPECTED
# when a hook rewrote something; that is not a failure yet.
echo "==> pre-commit pass 1 (auto-fixers may rewrite files)"
set +e
.venv/bin/pre-commit run
pass1=$?
set -e

if [ "$pass1" -ne 0 ]; then
    # Re-stage anything the hooks fixed, so the commit contains the fixed form.
    git add -u
    echo "==> pre-commit pass 2 (verify clean)"
    if ! .venv/bin/pre-commit run; then
        echo "pre-commit still failing after auto-fix -- fix the reported issues" >&2
        exit 1
    fi
fi

git commit "$@"
echo "==> committed: $(git log --oneline -1)"
