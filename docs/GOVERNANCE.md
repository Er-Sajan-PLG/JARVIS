# JARVIS Governance — Living Document v3.0.0

**Status**: ACTIVE
**Authority**: This document governs all changes to JARVIS repository
**Workflow Orchestration**: n8n (external) — all CI/CD, automation, approval flows run in n8n
**Last Updated**: 2026-09-10

---

## 1. Decision-Making Authority

| Decision Type | Authority | Process |
|---------------|-----------|---------|
| **Architecture changes** | Architecture Review (n8n workflow) | ADR proposal → review → merge |
| **Security policy** | Security Review (n8n workflow) | Threat model → approval → enforce |
| **Dependency updates** | Dependabot + n8n auto-merge | Auto-merge on green CI (patch/minor) |
| **Breaking API changes** | API Contract Review | Deprecation notice → migration window → remove |
| **Infrastructure** | Infrastructure as Code (n8n) | Terraform/Ansible via n8n workflows |
| **Release** | Automated (n8n + semantic-release) | Conventional commits → auto-version → tag |

**No direct pushes to `main`** — all changes via PR with n8n-enforced gates.

> **Versioning note**: the version number is **derived from git tags**, not
> from a file — see `docs/VERSIONING.md`. `pyproject.toml` `project.version` is
> metadata kept in sync by `scripts/bump_version.py`, never the authority.

---

## 2. Branching Model (n8n-Enforced)

```
main (protected)
   │
   ├── feature/*     → PR → n8n CI → review → squash merge
   ├── fix/*         → PR → n8n CI → review → squash merge
   ├── chore/*       → PR → n8n CI → auto-merge (if green)
   ├── docs/*        → PR → n8n CI → auto-merge (if green)
   └── release/*     → PR → n8n CI → tag → deploy
```

**Branch Protection Rules (enforced via n8n + GitHub API)**:
- ✅ Required: PR from feature branch
- ✅ Required: n8n CI workflow passes (lint, typecheck, test, build)
- ✅ Required: 1 approval (code owner for critical paths)
- ✅ Required: No force push
- ✅ Required: Linear history (squash merge)
- ✅ Required: Signed commits

---

## 3. n8n Workflow Governance

### 3.1 n8n as Single Source of Automation Truth

All automation lives in n8n — **no GitHub Actions for business logic**.

| Workflow Category | n8n Workflow | Trigger |
|-------------------|--------------|---------|
| **CI Pipeline** | `JARVIS-CI` | PR opened/updated |
| **CD Deploy** | `JARVIS-Deploy` | Tag pushed / main merged |
| **Dependency Updates** | `JARVIS-Dependabot` | Dependabot PR created |
| **Security Scan** | `JARVIS-Security` | Schedule (daily) + PR |
| **Release Automation** | `JARVIS-Release` | Conventional commit to main |
| **HITL Approval** | `JARVIS-HITL` | JARVIS emits HITLRequestEvent |
| **Workflow Cleanup** | `JARVIS-Cleanup` | Schedule (weekly) |

### 3.2 n8n Workflow Standards

- **Version controlled**: Workflows exported as JSON → committed to `n8n/workflows/`
- **Environment promotion**: Dev → Staging → Prod via n8n environments
- **Secrets**: Stored in n8n encrypted credentials (never in repo)
- **Observability**: All workflows emit to JARVIS telemetry via REST API
- **Rollback**: One-click in n8n UI; `JARVIS-Rollback` workflow for emergencies

---

## 4. Quality Gates (n8n CI Pipeline)

### 4.1 Required Checks (All Must Pass)

```yaml
# n8n CI workflow: JARVIS-CI
stages:
  - lint:
      - ruff check app/ tests/
      - ruff format --check app/ tests/
  - typecheck:
      - mypy --strict app/
  - test:
      - pytest tests/ -v --cov=app --cov-fail-under=80
  - build:
      - python -m compileall app/
      - docker build -t jarvis:${GIT_SHA} .
  - security:
      - gitleaks detect --source .
      - pip-audit -r requirements.txt
  - contract:
      - python -c "from app.main import app; from app.bootstrap import bootstrap_system"
```

### 4.2 Gate Enforcement

| Gate | Enforced By | Bypass |
|------|-------------|--------|
| Lint | n8n CI | ❌ Never |
| Typecheck | n8n CI | ❌ Never |
| Tests (80% coverage) | n8n CI | ❌ Never |
| Build | n8n CI | ❌ Never |
| Security scan | n8n CI | ❌ Never |
| Import smoke test | n8n CI | ❌ Never |
| Branch protection | GitHub + n8n | ❌ Never |

---

## 5. Security Governance

### 5.1 Secret Management

| Secret Type | Storage | Rotation |
|-------------|---------|----------|
| `JARVIS_API_KEY` | n8n encrypted credentials | 90 days (n8n workflow) |
| LLM API keys | `.env` (local) / n8n credentials (prod) | Per provider policy |
| Database credentials | n8n credentials | 90 days |
| n8n encryption key | Host secret manager | Annual |

### 5.2 Vulnerability Management

- **Dependabot**: Enabled, grouped PRs, weekly schedule
- **Auto-merge**: Patch/minor on green CI; major requires review
- **SAST**: CodeQL via n8n weekly + on PR
- **Container scan**: Trivy on every image build
- **SBOM**: CycloneDX generated on release

### 5.3 Incident Response

1. n8n alert → Security workflow triggered
2. Auto-isolate (revoke API key, block IP)
3. Create incident ticket (n8n → Linear/GitHub Issues)
4. Post-mortem within 72h → ADR if architectural

---

## 6. Release & Versioning

### 6.1 Semantic Versioning (Strict)

| Version | Trigger | Example |
|---------|---------|---------|
| **MAJOR** | Breaking API change, architecture shift | 3.0.0 → 4.0.0 |
| **MINOR** | New capability, non-breaking | 3.0.0 → 3.1.0 |
| **PATCH** | Bug fix, security patch | 3.0.0 → 3.0.1 |

### 6.2 Release Automation (n8n)

```
Conventional commit to main
       │
       ▼
n8n: JARVIS-Release workflow
       │
       ├─ Parse commit types (feat/fix/chore/breaking)
       ├─ Determine version bump
       ├─ Generate CHANGELOG.md (auto + manual breaking section)
       ├─ Create signed tag (vX.Y.Z)
       ├─ Build & push Docker image (multi-arch)
       ├─ Deploy to staging (n8n: JARVIS-Deploy-Staging)
       ├─ Run smoke tests against staging
       ├─ Promote to production (manual approval in n8n)
       └─ Notify (n8n: Slack/Email/Telegram)
```

### 6.3 Changelog Format

```markdown
## [3.1.0] - 2026-09-15

### Added
- New capability: X (feat: ...)

### Changed
- Modified behavior: Y (chore: ...)

### Fixed
- Bug fix: Z (fix: ...)

### Security
- CVE-XXXX patched (fix: ...)

### Breaking Changes
- [Manual entry required for breaking commits]
```

---

## 7. Code Standards

### 7.1 Python (Enforced by ruff + mypy)

```toml
# pyproject.toml (source of truth)
[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "F", "I", "UP", "B", "C4", "PTH", "PIC", "PL", "T20", "ARG", "SIM", "RET"]
ignore = []

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### 7.2 Commit Convention (Enforced)

```
<type>(<scope>): <description>

[optional body]

[optional footer: BREAKING CHANGE, Closes #XXX]
```

| Type | Meaning | Version Bump |
|------|---------|--------------|
| `feat` | New capability | MINOR |
| `fix` | Bug fix | PATCH |
| `chore` | Maintenance, deps | PATCH |
| `docs` | Documentation only | NONE |
| `refactor` | Code restructure | NONE |
| `test` | Test changes | NONE |
| `breaking` | **Breaking change** | MAJOR |

---

## 8. Documentation Standards

| Document | Location | Update Trigger | Owner |
|----------|----------|----------------|-------|
| **ARCHITECTURE.md** | `docs/ARCHITECTURE.md` | Architectural change | Arch Review |
| **API_CONTRACT.md** | `docs/API_CONTRACT.md` | API change | API Review |
| **GOVERNANCE.md** | `docs/GOVERNANCE.md` | Process change | All |
| **ROADMAP.md** | `docs/ROADMAP.md` | Sprint planning | Product |
| **DEVELOPMENT.md** | `docs/DEVELOPMENT.md` | Tooling change | Dev Team |
| **CAPABILITY_TRACKER.md** | `docs/CAPABILITY_TRACKER.md` | Contract milestone | Arch Review |
| **ADR-XXX** | `docs/adr/ADR-XXX.md` | Architectural decision | Author + Review |

**Rule**: Documentation updated in same PR as code change. No separate docs PR.

---

## 9. Capability Contract Compliance (JARVIS ↔ PROFESSOR-J)

| Capability | JARVIS Status | Tracking |
|------------|---------------|----------|
| Cognitive Engine (LangGraph) | 🟡 To port from PROFESSOR-J | `CAPABILITY_TRACKER.md` |
| Memory (rich schema, hybrid) | 🟡 Partial (v3.0 has hybrid) | `CAPABILITY_TRACKER.md` |
| Provider Routing | ✅ Implemented | `CAPABILITY_TRACKER.md` |
| Safety Gate (HITL) | ✅ Implemented | `CAPABILITY_TRACKER.md` |
| MCP Client | 🟡 To port | `CAPABILITY_TRACKER.md` |
| Voice I/O | 🔵 Not in scope | N/A |
| Session/Checkpoint | ✅ Implemented | `CAPABILITY_TRACKER.md` |

**Governance**: Capability Contract changes require coordinated rollout in both repos. See `CAPABILITY_TRACKER.md`.

---

## 10. Compliance & Audit

| Audit Type | Frequency | Tool | Output |
|------------|-----------|------|--------|
| **Forensic Architecture** | Quarterly | `forensic-architecture-audit` skill | Gap report |
| **USAT Audit** | Monthly | `usat` CLI | Hygiene score |
| **Security Scan** | Daily | n8n + CodeQL + gitleaks | SARIF + alerts |
| **Dependency Audit** | Weekly | Dependabot + pip-audit | PR + report |
| **License Compliance** | Per release | REUSE / licensee | SPDX report |

---

## 11. Escalation Path

| Level | Trigger | Response Time | Owner |
|-------|---------|---------------|-------|
| **P0 - Production Down** | Health check fail, 5xx > 5% | 15 min | On-call (n8n alert) |
| **P1 - Security Breach** | Secret leaked, vuln exploited | 30 min | Security lead |
| **P2 - CI Broken** | Main branch red | 1 hour | Dev lead |
| **P3 - Capability Gap** | Contract milestone missed | 1 sprint | Architecture |

---

## 12. Change Log (Governance Itself)

| Version | Date | Change | Author |
|---------|------|--------|--------|
| 3.0.0 | 2026-09-10 | Initial governance from forensic audit | Hermes |

---

**Next**: See `ROADMAP.md` for prioritized rebuild plan, `DEVELOPMENT.md` for daily workflow, `API_CONTRACT.md` for API surface.
