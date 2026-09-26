#!/usr/bin/env bash
# JARVIS one-command setup (autonomous docs system: hook installation is part
# of setup, not a manual step anyone can forget).
#
# Installs: venv + frozen deps + pre-commit framework + native githooks +
# JARVIS_API_KEY. Idempotent and non-interactive — safe to re-run.
# Replaces the manual sequences in docs/DEVELOPMENT.md §1 (kept as fallback).
#
# Offline-tolerant: dependency installation is SKIPPED when the imports already
# resolve (air-gapped re-runs must not fail on an unreachable index).
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || dirname "$(readlink -f "$0")"/..)"
cd "$REPO_ROOT"

# 1. Virtualenv (Python 3.11+ required by pyproject.toml).
if [ ! -x ".venv/bin/python" ]; then
  echo "→ creating .venv"
  python3.11 -m venv .venv 2>/dev/null || python3 -m venv .venv
fi

# 2. Frozen dependencies — only when imports are missing.
if ! .venv/bin/python -c "import fastapi, pydantic, chromadb" 2>/dev/null; then
  echo "→ installing requirements.txt"
  .venv/bin/pip install --upgrade pip -q
  .venv/bin/pip install -r requirements.txt
else
  echo "→ dependencies present (skipping pip)"
fi

# 3. Pre-commit framework (deliberately NOT in requirements.txt, which is the
#    frozen runtime set — installed here so fresh clones always get it).
if ! .venv/bin/python -c "import pre_commit" 2>/dev/null; then
  echo "→ installing pre-commit framework"
  .venv/bin/pip install -q "pre-commit==4.6.2"
else
  echo "→ pre-commit framework present (skipping pip)"
fi

# 4. Framework hooks (ruff, mypy, gitleaks, commitlint, docs Layer 1). When
# core.hooksPath is set the framework refuses to install into .git/hooks —
# that is FINE: the native githooks/pre-commit invokes `.venv/bin/pre-commit
# run` directly, so the framework config is honored without installed shims.
echo "→ installing framework hooks"
if .venv/bin/pre-commit install --install-hooks >/dev/null 2>&1; then
  echo "   framework hooks installed"
else
  echo "   framework shim skipped (core.hooksPath set; native hook runs it)"
fi

# 5. Native hooks (version guard, fact sync, pre-push gate) via hookspath.
echo "→ activating native githooks"
.venv/bin/python scripts/bump_version.py install-hooks >/dev/null

# 6. API key for local runs.
if ! grep -q "^JARVIS_API_KEY=.\+" .env 2>/dev/null; then
  echo "→ generating JARVIS_API_KEY"
  printf 'JARVIS_API_KEY=%s\n' "$(openssl rand -hex 32)" >> .env
else
  echo "→ JARVIS_API_KEY present (leaving .env alone)"
fi

# 7. Verify: hooks resolve, manifest validates, app imports.
echo "→ verifying"
git config core.hooksPath
.venv/bin/python scripts/docs/manifest-validate.py | tail -1
.venv/bin/python -c "import app.bootstrap; print('app imports ok')"
echo "✅ setup complete — hooks enforced on every commit from here on"
