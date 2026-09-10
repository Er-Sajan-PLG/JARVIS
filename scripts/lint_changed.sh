#!/usr/bin/env bash
# Ratchet lint: ruff-check only the Python files CHANGED in this PR/push.
#
# Rationale: the repo carries pre-existing lint debt (RISK-005 in
# docs/ACCEPTED_RISKS.md). Enforcing ruff on the whole tree fails at HEAD and
# blocks every PR. This checks changed files only, so new/modified code must be
# clean while the legacy backlog is burned down per sprint.
#
# Usage (CI):   scripts/lint_changed.sh
# Usage (local): scripts/lint_changed.sh <base-ref>
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

BASE="${1:-}"
if [ -z "$BASE" ]; then
  if [ -n "${GITHUB_BASE_REF:-}" ]; then
    BASE="origin/${GITHUB_BASE_REF}"
  elif git rev-parse --verify -q HEAD^ >/dev/null; then
    BASE="HEAD^"
  else
    BASE=""
  fi
fi

if [ -n "$BASE" ] && git rev-parse --verify -q "$BASE" >/dev/null; then
  # Compare BASE to the WORKING TREE (not BASE...HEAD) so locally staged/unstaged
  # edits are caught too — in CI the tree is clean so this equals the commit range.
  CHANGED="$(git diff --name-only --diff-filter=ACMR "$BASE" -- '*.py' || true)"
else
  CHANGED="$(git ls-files '*.py' || true)"
fi

if [ -z "$CHANGED" ]; then
  echo "✅ ratchet lint: no changed Python files"
  exit 0
fi

echo "🔍 ratchet lint: $(echo "$CHANGED" | wc -l) changed Python file(s)"
echo "$CHANGED"
# shellcheck disable=SC2086
.venv/bin/ruff check $CHANGED