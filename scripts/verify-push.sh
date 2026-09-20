#!/usr/bin/env bash
# scripts/verify-push.sh — bypass detector (Sprint: extreme free-tier hardening).
#
# Hooks live on disk and can be skipped with --no-verify. This script is the
# backstop: given a pushed range (default: origin/main..HEAD), it verifies
# every commit AFTER the fact — signatures, secrets, and CI status — and
# reports what slipped through. Run it after any push you did not personally
# watch go through the pre-push hook, or on a schedule (n8n/cron).
#
# Exit 0 = clean. Exit 1 = something reached remote that should not have.
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
RANGE="${1:-origin/main..HEAD}"
FAIL=0

echo "🔍 verify-push over $RANGE"

# 1. Signatures on every commit in range.
while read -r sha; do
  [ -z "$sha" ] && continue
  sig="$(git -C "$REPO_ROOT" log -1 --format="%G?" "$sha" 2>/dev/null || echo N)"
  if [ "$sig" != "G" ] && [ "$sig" != "U" ]; then
    echo "❌ unsigned: $sha $(git -C "$REPO_ROOT" log -1 --format="%s" "$sha")"
    FAIL=1
  fi
done < <(git -C "$REPO_ROOT" rev-list "$RANGE" 2>/dev/null)
[ "$FAIL" -eq 0 ] && echo "✅ signatures ok."

# 2. Secrets across the range (gitleaks git-aware scan of these commits).
if command -v gitleaks >/dev/null 2>&1; then
  if git -C "$REPO_ROOT" rev-list "$RANGE" 2>/dev/null | head -1 >/dev/null; then
    if gitleaks detect --source "$REPO_ROOT" --log-opts="$RANGE" --redact >/dev/null 2>&1; then
      echo "✅ secrets ok."
    else
      echo "❌ gitleaks flagged the range (see above)."
      FAIL=1
    fi
  fi
else
  echo "⚠️ gitleaks binary missing — secrets NOT verified."
  FAIL=1
fi

# 3. CI status of the pushed HEAD (informational: red here means revert).
HEAD_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
if command -v gh >/dev/null 2>&1; then
  STATE="$(gh api "repos/Er-Sajan-PLG/JARVIS/commits/$HEAD_SHA/status" --jq '.state' 2>/dev/null || echo unknown)"
  echo "ℹ️ remote combined status for $HEAD_SHA: $STATE"
  if [ "$STATE" = "failure" ] || [ "$STATE" = "error" ]; then
    echo "❌ remote CI is red on pushed HEAD — revert or fix forward immediately."
    FAIL=1
  fi
else
  echo "⚠️ gh missing — remote CI status unchecked."
fi

if [ "$FAIL" -ne 0 ]; then
  echo ""; echo "❌ VERIFY FAILED — something slipped through. Revert or remediate, then push clean."
  exit 1
fi
echo ""; echo "✅ VERIFY PASSED — remote is clean."
