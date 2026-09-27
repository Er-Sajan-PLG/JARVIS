#!/usr/bin/env bash
# Canonical docs pipeline entry point (docs-as-code UX).
# Delegates to the existing scripts; adds no logic of its own.
#   ./scripts/docs.sh sync   — regenerate derived docs (review + stage the diff)
#   ./scripts/docs.sh fast   — Layer 1 staged-scope check (pre-commit runs this)
#   ./scripts/docs.sh check  — Layer 2 full-tree check (pre-push/CI runs this)
#   ./scripts/docs.sh ci     — the exact gate set CI runs (offline subset)
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || dirname "$(readlink -f "$0")"/..)"
cd "$REPO_ROOT"
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

cmd="${1:-check}"
case "$cmd" in
  sync)
    "$PY" scripts/docs/generate.py --apply
    "$PY" scripts/sync_doc_facts.py --sync
    ;;
  fast)
    "$PY" scripts/docs/check-changed.py
    ;;
  check)
    "$PY" scripts/docs/check-full.py
    ;;
  ci)
    "$PY" scripts/docs/manifest-validate.py
    "$PY" scripts/docs/check-full.py
    "$PY" scripts/sync_doc_facts.py --check
    ;;
  *)
    echo "usage: $0 {sync|fast|check|ci}" >&2
    exit 2
    ;;
esac
