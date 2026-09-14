# JARVIS Governance

**Status**: ACTIVE
**Type**: governance
**Source**: `scripts/ci_gate.py`, `scripts/ci_bridge.py` at HEAD
**Last Updated**: 2026-09-13

**Authority**: This document governs all changes to JARVIS repository
**Workflow Orchestration**: n8n (external) **schedules**; JARVIS **decides**.
See `docs/adr/ADR-013-jarvis-orchestrates-n8n-executes.md`.

---

## 1. Decision-Making Authority

| Decision Type | Authority | Process |
|---------------|-----------|---------|
| **Architecture changes** | Architecture Review (human) | ADR proposal → review → merge |
| **Security policy** | Security Review (human) | Threat model → approval → enforce |
| **Dependency updates** | Local gate → auto-merge (see note) | Auto-merge on green gate (patch/minor) |
| **Breaking API changes** | API Contract Review (human) | Deprecation notice → migration window → remove |
| **Infrastructure** | Repo scripts + systemd user units | Version-controlled scripts, not a workflow node |
| **Release** | `githooks/pre-push` → `scripts/version_bump.py` | Conventional commits → auto-bump → tag → GitHub Release |

**No direct pushes to `main`** — changes go through a PR whose gate result is
published by the local CI plane.

> **Corrected 2026-09-13.** This table previously attributed every decision to an
> n8n workflow (`Architecture Review (n8n workflow)`, `Infrastructure as Code
> (n8n)`, `Release — Automated (n8n + semantic-release)`). None of those
> workflows exist; there is no `semantic-release` in this repo, and the release
> number is cut by `githooks/pre-push` calling `scripts/version_bump.py`. Per
> **ADR-013**, deterministic decisions belong in code this repository owns — n8n
> schedules and notifies. The three workflows that do exist are named in §3.
>
> **On "Dependency updates → auto-merge":** GitHub-side auto-merge is *not
> available* on this repository (`allow_auto_merge: false`, not settable on the
> Free private plan). The local bridge currently publishes a verdict but does not
> merge; Dependabot PRs therefore accumulate. See
> `docs/CI-TOKEN-PERMISSIONS.md` §5 for the measured state and what unblocks it.

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

**Branch protection: NOT available on this repository.** Measured 2026-09-12:
`GET /repos/Er-Sajan-PLG/JARVIS/branches/main/protection` → **HTTP 403**
("Upgrade to GitHub Pro or make this repository public"). Nothing on that endpoint
can be configured, so **no** rule above is enforced by GitHub.

| Rule | Real status |
|------|-------------|
| Required PR | **Convention only** — `main` can be pushed to directly |
| Gate passes | **Published as commit statuses, cannot block merge** (RISK-012) |
| 1 approval | Not enforced — solo repo; GitHub forbids self-approval |
| No force push | Not enforced |
| Linear history | Convention (squash merge is the practice) |
| Signed commits | Not enforced — commits report `N`/`E`, not verified (RISK-011) |

Until the platform limit changes, enforcement is **process, not policy**: the gate
publishes statuses, the pipeline stops on red, and a human does not press merge.
That is an accepted risk with an owner and a review date — see `docs/ACCEPTED_RISKS.md`
(RISK-012, RISK-011).

---

## 3. n8n Workflow Governance

### 3.1 n8n schedules; the gate decides (ADR-013)

**Corrected 2026-09-12.** This section previously declared n8n the "Single Source
of Automation Truth" and named seven workflows. Three exist, and none of them
decides anything — they trigger and notify. See
`docs/adr/ADR-013-jarvis-orchestrates-n8n-executes.md` for the decision.

The automation that actually runs:

| Workflow | Trigger | What it actually does |
|----------|---------|------------------------|
| `JARVIS-CI-Local` | Schedule (poll) | Calls `scripts/ci_bridge.py`, which gates each PR's head SHA with `scripts/ci_gate.py` (<!--fact:gate_count-->26<!--/fact--> checks) and publishes <!--fact:context_count-->9<!--/fact--> commit-status contexts |
| `JARVIS-HITL` | Schedule (poll `GET /api/v1/hitl/pending`) | Notifies a human that a DESTRUCTIVE step is paused; calls the decision webhook |
| `JARVIS-Cleanup` | Schedule (weekly) | Deletes merged branches and stale workflow runs |

**The decision is not in n8n.** `scripts/ci_gate.py` runs the <!--fact:gate_count-->26<!--/fact--> checks and decides
pass/fail; `ci_bridge.py` records the result. n8n's CI workflow only *calls* the
bridge and relays the outcome. A workflow that named itself the decision-maker
was never the one making the decision.

> Workflows live in `n8n/workflows/*.json`, are imported into the running n8n DB,
> and are edited through the UI by the owner — see `docs/N8N-HANDOVER.md`.

### 3.2 n8n Workflow Standards

- **Version controlled**: Workflows exported as JSON → committed to `n8n/workflows/`
- **Environment promotion**: Dev → Staging → Prod via n8n environments
- **Secrets**: Stored in n8n encrypted credentials (never in repo)
- **Observability**: All workflows emit to JARVIS telemetry via REST API
- **Rollback**: Revert the offending commit / restore from the repo copy. There is
  no `JARVIS-Rollback` workflow; an n8n UI button is not an enforcement path
  (ADR-013).

---

## 4. Quality Gates (n8n CI Pipeline)

### 4.1 Required Checks (All Must Pass)

There is no `JARVIS-CI` n8n workflow and no YAML describing one. The real gate is
`scripts/ci_gate.py` — **<!--fact:gate_count-->26<!--/fact--> checks** run against a detached worktree of the target
commit, grouped into **8 published commit-status contexts**:

| Published context | Checks behind it |
|---|---|
| `Lint & Typecheck` | `ruff_ratchet` (changed files only), `mypy` (ratcheted at `.governance/mypy_baseline.txt`) |
| `SAST` | `semgrep` |
| `Tests` | `pytest` (<!--fact:test_count-->1240<!--/fact--> tests), `contract`, `coverage` |
| `Security Scan` | `gitleaks`, `trufflehog`, `bandit`, `pip_audit` |
| `Supply Chain` | `trivy`, `osv`, `licenses`, `sbom`, `provenance`, `checkov` |
| `Virtual Board Governance` | `board` (8 AST checks in `scripts/board/review.py`) |
| `Build` | `compileall`, `hadolint`, `docker_build`, `worktree` |
| `Conventional Commits` | `commitlint` |

Full threat model and per-check detail: `docs/CI-GATE-SOTA.md`.

### 4.2 Gate Enforcement

| Gate | Enforced By | Bypass |
|------|-------------|--------|
| Lint | `ci_gate.py` (`ruff_ratchet`) | ❌ Never |
| Typecheck | `ci_gate.py` (`mypy`, ratcheted) | ❌ Never |
| Tests | `ci_gate.py` (`pytest`, `contract`, `coverage`) | ❌ Never |
| Build | `ci_gate.py` (`compileall`, `hadolint`, `docker_build`) | ❌ Never |
| Security scan | `ci_gate.py` (`gitleaks`, `trufflehog`, `bandit`, `pip_audit`) | ❌ Never |
| Import smoke test | `ci_gate.py` (`contract`) | ❌ Never |
| Branch protection | **NOT AVAILABLE** (GitHub 403, RISK-012) | ⚠️ Any push can bypass |

---

## 5. Security Governance

### 5.1 Secret Management

| Secret Type | Storage | Rotation |
|-------------|---------|----------|
| `JARVIS_API_KEY` | `.env` (local, gitignored) | Manual |
| LLM API keys | `.env` (local) / `.ci-bridge.env` | Per provider policy |
| CI GitHub token | `.ci-bridge.env` (service env file, 0600) | Per PAT/App policy (ADR-012) |
| Database credentials | N/A — no database in use | — |
| n8n encryption key | n8n default location on this host | Not automated |

> **Corrected 2026-09-12.** This table previously claimed rotation *workflows* that
> do not exist. Rotation is manual; no scheduled rotation job runs.

### 5.2 Vulnerability Management

- **Dependabot**: Enabled, grouped PRs, weekly schedule
- **Auto-merge**: Patch/minor on green CI; major requires review
- **SAST**: `semgrep` + `bandit` inside `scripts/ci_gate.py` on every gated commit.
  (CodeQL needs GitHub Actions, which is billing-disabled here — RISK-012.)
- **Container scan**: Trivy on every image build
- **SBOM**: CycloneDX generated on release

### 5.3 Incident Response

1. `gitleaks` / `trufflehog` / `bandit` / `pip_audit` fire inside `ci_gate.py`,
   or a gate result goes red → the pipeline stops (there is no separate
   `JARVIS-Security` workflow).
2. Isolate by hand: rotate the leaked credential, restart the service.
3. File the issue in GitHub.
4. Post-mortem within 72h → ADR if architectural.

---

## 6. Release & Versioning

### 6.1 Semantic Versioning (Strict)

| Version | Trigger | Example |
|---------|---------|---------|
| **MAJOR** | Breaking API change, architecture shift | 3.0.0 → 4.0.0 |
| **MINOR** | New capability, non-breaking | 3.0.0 → 3.1.0 |
| **PATCH** | Bug fix, security patch | 3.0.0 → 3.0.1 |

### 6.2 Release Automation (n8n)

**There is no `JARVIS-Release` workflow and no `JARVIS-Deploy-Staging`.** Release
automation is blocked at two points that are recorded, not hidden:

| Step | Real status |
|------|-------------|
| Determine version bump | `scripts/bump_version.py patch\|minor\|major` — **manual invocation** |
| CHANGELOG.md | Written by hand / by `bump_version.py` |
| Tag `vX.Y.Z` | `git tag` (not GPG-signed — RISK-011) |
| Build & push image | `docker build` locally; no registry push configured |
| Deploy to staging | **Not implemented** — no staging environment exists |
| Smoke tests | **Not implemented** against a deployed environment |
| Promote to production | **Not implemented** |
| Notify | n8n can send the message; nothing currently triggers it |

Full automation requires GitHub Actions for the hosted half and is blocked by the
billing limit on this private repo (RISK-012, TD-009 in `docs/ROADMAP.md`).

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
| 3.0.1 | 2026-09-12 | §2/§3/§4 corrected to measured reality: three real n8n workflows (not seven), the real `ci_gate.py` 22-check/8-context gate (not a fictional n8n CI YAML), and branch protection recorded as **403-unavailable** rather than six ✅ rows. Authority settled by ADR-013. | Hermes |

---

**Next**: See `ROADMAP.md` for prioritized rebuild plan, `DEVELOPMENT.md` for daily workflow, `API_CONTRACT.md` for API surface.
