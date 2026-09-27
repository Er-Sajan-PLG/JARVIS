# JARVIS Development Workflow

**Status**: ACTIVE
**Type**: guide
**Last Updated**: 2026-09-13
**Reviewed**: 2026-09-14

**Orchestration**: JARVIS decides, n8n schedules (ADR-013)

---

## 1. Local Development Setup

### 1.1 One-Command Setup

> There is no `JARVIS-Setup-Env` n8n workflow, and there is no setup shell
> script either — environment setup is the venv + pip flow below, and
> versioning is git tags (see §9). Do not look for
> `scripts/setup_dev_env.sh`, `requirements-dev.txt` or `.releaserc.json`:
> none of them exist in this tree.

Preferred (one command, installs hooks too):

```bash
cd /home/sajan/Projects/JARVIS && ./scripts/setup.sh
```

Manual fallback:

```bash
# Run once per machine
cd /home/sajan/Projects/JARVIS
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pre-commit install

# Generate a key and write it into .env
grep -q JARVIS_API_KEY .env 2>/dev/null || \
  printf 'JARVIS_API_KEY=%s\n' "$(openssl rand -hex 32)" >> .env
```

**What it does**:
1. Creates `.venv` with Python 3.11/3.12 (`requires-python = ">=3.11"`)
2. Installs `requirements.txt` (the single frozen dependency set)
3. Generates `JARVIS_API_KEY` if missing
4. Installs pre-commit hooks (ruff, mypy, gitleaks)
5. Verifies: `.venv/bin/python -m app.main` starts cleanly

### 1.2 Manual Setup (if needed)

```bash
# Python version MUST be 3.11 or 3.12
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pre-commit install

# Add API key if missing
grep -q JARVIS_API_KEY .env || echo "JARVIS_API_KEY=$(openssl rand -hex 32)" >> .env
```

### 1.3 Verify Setup

```bash
# Should start without errors
.venv/bin/python -m app.main

# Health check
curl -H "Authorization: Bearer $JARVIS_API_KEY" http://localhost:8000/api/v1/health
```

### 1.4 Commit signing (required — pushes are rejected without it)

```bash
# One time per machine: generate a key, add the .pub to GitHub → Settings → SSH keys
ssh-keygen -t ed25519 -C "you@example.com"   # skip if you already have one
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true
# Verify: make any commit, then `git log --show-signature -1` must show Good.
```

---

## 2. Daily Workflow

### 2.1 Start Work

```bash
cd /home/sajan/Projects/JARVIS
source .venv/bin/activate

# Create feature branch
git checkout main && git pull
git checkout -b feature/your-feature-name

# Start n8n dev environment (if needed)
n8n start  # plain start; the bridge listens on 127.0.0.1:8770, no tunnel flag
```

### 2.2 Code Changes

```bash
# Edit code in app/
# Run tests locally
pytest tests/ -v

# Check types
mypy app/

# Check style
ruff check app/
ruff format app/
```

### 2.3 Pre-Commit (Automatic)

```bash
# Runs on every commit via pre-commit hook
# - ruff check + format
# - mypy --strict
# - gitleaks detect
# - compileall (syntax check)
```

### 2.4 Push & PR

```bash
git add -A
git commit -m "feat(scope): description

Body if needed

Closes #XXX"
git push origin feature/your-feature-name

# Create PR via GitHub CLI or UI
gh pr create --title "feat(scope): description" --body "..."

# n8n CI runs automatically
```

---

## 3. n8n Workflow Development

### 3.1 Workflow Structure

All n8n workflows live in `n8n/workflows/` as JSON exports:

```
n8n/
├── workflows/
│   ├── JARVIS-Local-CI.json   # polls scripts/ci_bridge.py -> scripts/ci_gate.py
│   ├── JARVIS-HITL.json       # polls GET /api/v1/hitl/pending, calls decision webhook
│   └── JARVIS-Cleanup.json    # weekly: merged branches + stale workflow runs
├── credentials/          # NOT committed (encrypted in n8n)
└── README.md            # Workflow documentation
```

**Only three workflows exist.** There is no `JARVIS-CI`, `JARVIS-Deploy`,
`JARVIS-Release`, `JARVIS-Security`, or `JARVIS-Setup-Env` — those were planned
names in an earlier draft. The CI decision lives in `scripts/ci_gate.py`; n8n
schedules the poll that invokes it (ADR-013).

### 3.2 Workflow Development Process

1. **Develop in n8n UI** (dev environment)
2. **Export JSON** → commit to `n8n/workflows/`
3. **Test in n8n staging** environment
4. **Promote to production** via n8n environment promotion
5. **Document** in `n8n/README.md`

### 3.3 n8n ↔ JARVIS Integration

| n8n Workflow | JARVIS Endpoint | Purpose |
|--------------|-----------------|---------|
| `JARVIS-HITL` | `GET /api/v1/hitl/pending` + decision webhook | Human approval for DESTRUCTIVE tools |
| `JARVIS-CI-Local` (file: `n8n/workflows/JARVIS-Local-CI.json`) | `POST localhost:8770/run` (bridge) | Triggers `ci_bridge.py`, which gates PR heads |
| `JARVIS-Cleanup` | GitHub API | Deletes merged branches and stale runs |

`WS /ws/chat` now requires the same `JARVIS_API_KEY` bearer credential as the
REST surface (Phase 0 F4) — a browser cannot set that header, so an n8n workflow
is not the right client for it.

### 3.4 Integration endpoints you will call in development

Comms/voice surfaces (full reference: `docs/COMMS.md`, `docs/VOICE.md`).
All require `Authorization: Bearer $JARVIS_API_KEY`.

```bash
# Unified notify dispatcher (channels: push, telegram, whatsapp; default push)
curl -s -X POST http://127.0.0.1:8000/api/v1/notify/ \
  -H "Authorization: Bearer $JARVIS_API_KEY" -H 'Content-Type: application/json' \
  -d '{"title":"dev","body":"hello from dev","channels":["push"]}'

# Morning brief: generate, or generate + deliver (slack/email/push)
curl -s -H "Authorization: Bearer $JARVIS_API_KEY" http://127.0.0.1:8000/api/v1/brief/
curl -s -X POST -H "Authorization: Bearer $JARVIS_API_KEY" http://127.0.0.1:8000/api/v1/brief/deliver

# Email: list / search / send / reply
curl -s -H "Authorization: Bearer $JARVIS_API_KEY" 'http://127.0.0.1:8000/api/v1/emails/?limit=5'
curl -s -X POST -H "Authorization: Bearer $JARVIS_API_KEY" -H 'Content-Type: application/json' \
  -d '{"to":"<recipient>","subject":"hi","body":"test"}' \
  http://127.0.0.1:8000/api/v1/emails/

# Voice: status (no model load), TTS; STT takes multipart audio
curl -s -H "Authorization: Bearer $JARVIS_API_KEY" http://127.0.0.1:8000/api/v1/voice/status
curl -s -X POST -H "Authorization: Bearer $JARVIS_API_KEY" -H 'Content-Type: application/json' \
  -d '{"text":"hello"}' http://127.0.0.1:8000/api/v1/voice/tts -o /tmp/t.mp3

# Push: public VAPID key, then authed subscribe + test
curl -s http://127.0.0.1:8000/api/v1/push/vapid-public-key
```

### 3.5 Messaging env (Telegram / WhatsApp)

| Group | Variables | Notes |
|---|---|---|
| Telegram | `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS` | two-way + voice notes; chat ID allowlist enforced by `TelegramPoller` |
| WhatsApp | `WHATSAPP_ENABLED`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_TO`, `WHATSAPP_TEMPLATE` | send-only; first contact must use the approved template (Meta rule) |
| Email | `JARVIS_EMAIL_IMAP_HOST/PORT`, `JARVIS_EMAIL_SMTP_HOST/PORT`, `JARVIS_EMAIL_ADDRESS/PASSWORD` | IMAP/SMTP backing `api/v1/emails` |
| Push | `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL` | without keys, push skips instead of failing |

### 3.6 Mobile APK build

The APK wraps the web console via Capacitor (`mobile/`). Full flow:
`docs/MOBILE_ACCESS.md` §5.

```bash
cd /home/sajan/Projects/JARVIS/mobile
npm install
npm run build-apk   # sync-www → cap sync → gradlew assembleDebug
```

`mobile/capacitor.config.json` (`appId "dev.jarvis.app"`, `webDir "www"`)
is the shell identity; Server URL + API key are set on-device in
*Settings → Access* after install.

---

## 4. Testing Standards

### 4.1 Test Organization

```
tests/
├── unit/           # Pure unit tests (fast, no external deps)
├── integration/    # Real DB, real providers, containers
├── contract/       # API contract tests
├── performance/    # Load/stress tests
└── conftest.py     # Shared fixtures
```

### 4.2 Test Requirements

| Test Type | Coverage Target | Run In CI | Run Locally |
|-----------|-----------------|-----------|-------------|
| Unit | ≥ 90% | ✅ Every PR | ✅ Always |
| Integration | ≥ 70% | ✅ Every PR | ✅ Optional (needs containers) |
| Contract | 100% of endpoints | ✅ Every PR | ✅ Always |
| Performance | N/A | 🔵 Weekly | 🔵 Manual |

### 4.3 Test Fixtures

- Use `tests/conftest.py` for shared fixtures
- **No** hand-built literals in tests — use factories
- **No** wall-clock time, network, or global state dependencies
- Mock at boundaries (external APIs, DB), not internals

---

## 5. Code Standards

### 5.1 Python Style (Enforced by ruff + mypy)

```toml
# pyproject.toml — Source of truth
[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "F", "I", "UP", "B", "C4", "PTH", "PIC", "PL", "T20", "ARG", "SIM", "RET"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
disallow_untyped_defs = true
```

### 5.2 Architecture Rules (Enforced by Code Review)

| Rule | Enforcement |
|------|-------------|
| No circular imports | mypy + manual review |
| Package boundaries respected | Import graph check in CI |
| No god files (>800 lines) | ruff `C4` (complexity) |
| All public functions typed | mypy strict |
| No bare `except` | ruff `B001` |
| No mutable defaults | ruff `B006` |
| No `shell=True` in subprocess | ruff `S602` |

### 5.3 Import Order (ruff `I`)

```python
# 1. Stdlib
import asyncio
from pathlib import Path

# 2. Third-party
from fastapi import FastAPI

# 3. Local (app.*)
from app.bootstrap import bootstrap_system
from app.adapters import http_router
```

---

## 6. Git Workflow

### 6.1 Commit Convention (Enforced)

```
<type>(<scope>): <description>

[optional body]

[optional footer: BREAKING CHANGE, Closes #XXX]
```

| Type | Version Bump | Example |
|------|--------------|---------|
| `feat` | MINOR | `feat(brain): add intent analyzer` |
| `fix` | PATCH | `fix(memory): handle empty query` |
| `chore` | PATCH | `chore(deps): update chromadb` |
| `docs` | NONE | `docs(arch): update topology` |
| `refactor` | NONE | `refactor(models): simplify router` |
| `test` | NONE | `test(brain): add planner tests` |
| `breaking` | **MAJOR** | `breaking(api): change response format` |

### 6.2 Branch Naming

| Pattern | Purpose |
|---------|---------|
| `feature/<scope>-<short-desc>` | New capability |
| `fix/<scope>-<short-desc>` | Bug fix |
| `chore/<scope>-<short-desc>` | Maintenance |
| `docs/<scope>-<short-desc>` | Documentation |
| `release/v<version>` | Release preparation |

### 6.3 PR Requirements

- [ ] All CI checks pass (n8n)
- [ ] 1 approval (code owner for critical paths)
- [ ] No force push
- [ ] Linear history (squash merge)
- [ ] Signed commits
- [ ] Documentation updated in same PR

---

## 7. Debugging & Diagnostics

### 7.1 Local Debugging

```bash
# Start with debug logging
JARVIS_LOG_LEVEL=DEBUG .venv/bin/python -m app.main

# Debug specific module
.venv/bin/python -m pytest tests/unit/test_brain.py -v -s --log-cli-level=DEBUG
```

### 7.2 Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: app.prompt.builder` | Legacy server import | Archive legacy servers |
| `401 Unauthorized` | Missing/wrong `JARVIS_API_KEY` | Check `.env` |
| `ImportError: chromadb` | Venv not installed / wrong Python | Recreate venv with 3.11 |
| `pytest not found` | Deps not installed | `pip install -r requirements.txt` |

### 7.3 n8n Debugging

```bash
# n8n execution logs
sqlite3 ~/.n8n/database.sqlite \
  "select id,status,startedAt from execution_entity order by id desc limit 10;"

# Drive the CI bridge directly (what JARVIS-CI-Local does on a schedule)
curl -s -X POST localhost:8770/run -H 'Content-Type: application/json' \
     -d '{"pr": 57}'

# Or run the gate itself against a commit
.venv/bin/python scripts/ci_gate.py --sha <sha> --base main
```

---

## 8. Performance Profiling

```bash
# Profile CPU
python -m cProfile -o profile.stats -m app.main
# Analyze with snakeviz
snakeviz profile.stats

# Profile memory
python -m memray run -m app.main
memray flamegraph memray-*.bin
```

---

## 9. Release Process (Developer View)

```bash
# 1. Ensure main is green
git checkout main && git pull

# 2. Create release branch
git checkout -b release/v3.1.0

# 3. Bump the version (no semantic-release; version derives from git tags)
.venv/bin/python scripts/bump_version.py patch   # or minor | major

# 4. PR -> gate -> squash merge -> tag
git tag -a v3.1.0 -m "Release v3.1.0"           # not GPG-signed (RISK-011)
git push origin v3.1.0

# 5. There is no deploy target yet (TD-009). Verify locally:
curl -H "Authorization: Bearer $JARVIS_API_KEY" http://localhost:8000/api/v1/health
```

---

## 10. Tooling Reference

| Tool | Purpose | Config |
|------|---------|--------|
| `ruff` | Lint + format | `pyproject.toml` |
| `mypy` | Type check | `pyproject.toml` |
| `pytest` | Testing | `pyproject.toml` / `conftest.py` |
| `gitleaks` | Secret scan | `.gitleaks.toml` |
| `pre-commit` | Git hooks | `.pre-commit-config.yaml` |
| `n8n` | Workflow orchestration | `n8n/workflows/` |
| `docker` | Containerization | `Dockerfile`, `docker-compose.yml` |
| `bump_version` | Versioning (git tags are the authority) | `scripts/bump_version.py` |

---

## 11. Quick Reference Commands

```bash
# Development
source .venv/bin/activate
pytest tests/ -v
mypy app/
ruff check app/ && ruff format app/

# n8n (workflows: JARVIS-CI-Local, JARVIS-HITL, JARVIS-Cleanup)
N8N_USER_FOLDER=/home/sajan n8n export:workflow --id=<workflow-id> \
  --output=n8n/workflows/JARVIS-Local-CI.json --pretty

# Docker
docker build -t jarvis:dev .
docker compose up -d

# Release (no GPG signing key configured - RISK-011)
git tag -a v3.1.0 -m "Release v3.1.0"
git push origin v3.1.0
```

---

**Next**: See `API_CONTRACT.md` for API surface, `CAPABILITY_TRACKER.md` for contract compliance.
