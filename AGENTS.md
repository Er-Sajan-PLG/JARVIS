# JARVIS Agent Standards & Governance

**Status**: ACTIVE
**Type**: governance
**Source**: `githooks/`, `scripts/ci_gate.py`, `scripts/check_docs.py` at HEAD
**Last Updated**: 2026-09-13

> **Not to be confused with [`docs/AGENTS.md`](docs/AGENTS.md).** That file
> documents the `app/agents/` package. This file is the authoritative
> governance standard every agent must follow.

**Version**: 1.0.0
**Authority**: Architecture Review Board

---

## 1. Agent Operating Principles

### 1.1 Core Philosophy
- **Small Work at a Time**: One logical change per commit. No mega-commits.
- **Foundation First**: Never implement features without standards/governance in place.
- **Documentation as Code**: Every change updates relevant docs in same PR.
- **Test-First**: Write test → Run (fail) → Implement → Run (pass) → Refactor.
- **Modularity & Isolation**: Each module has single responsibility, clear boundaries, minimal deps.
- **Upgradability**: No breaking changes without ADR + migration plan + version bump.

### 1.2 Mandatory Workflow (Every Task)
```
1. READ → Understand existing code, ADRs, standards
2. PLAN → Write task breakdown, identify affected modules
3. TEST → Write failing test(s) first
4. IMPLEMENT → Minimal change to pass test
5. VERIFY → Run tests, lint, typecheck, governance checks
6. DOCUMENT → Update docs, ADR if architectural
7. COMMIT → Conventional commit, small scope
```

---

## 2. Code Standards (Enforced by CI)

### 2.1 Python Style
- **Formatter**: `ruff format` (line-length: 100)
- **Linter**: `ruff check` (E, F, W, I, UP, B, C4, SIM, PIE)
- **Type Checker**: `mypy --strict` on `app/`
- **Import Order**: stdlib → third-party → local (`isort` via ruff)
- **No**: bare `except`, mutable defaults, `shell=True`, `any` without justification

### 2.2 Architecture Boundaries (Enforced by `scripts/board/review.py`)
```
app.adapters      → app.bootstrap, app.brain
app.bootstrap     → app.brain, app.models, app.resources, app.memory, app.session, app.workspace, app.telemetry, app.prompt, app.guardrails, app.artifacts, app.tools
app.brain         → app.domain, app.events, app.guardrails
app.models        → app.resources
app.memory        → app.integrations
app.telemetry     → app.events
app.guardrails    → (standalone)
app.events        → (standalone)
```
**Violations = CI Failure**

### 2.3 Domain Purity
- `app/domain/` = Pure dataclasses only (no external deps except stdlib)
- No framework imports, no I/O, no side effects
- Enforced by governance check `domain_purity`

---

## 3. Testing Standards (Enforced by CI)

### 3.1 Test Organization
```
tests/
├── unit/           # Pure unit tests (fast, no external deps)
├── integration/    # Real DB, real providers, containers
├── contract/       # API contract tests
└── e2e/            # Full user journeys (Playwright)
```

### 3.2 Test Requirements
| Type | Coverage Target | Run In CI |
|------|-----------------|-----------|
| Unit | ≥ 90% on new code | ✅ Every PR |
| Integration | ≥ 70% | ✅ Every PR |
| Contract | 100% of endpoints | ✅ Every PR |
| E2E | Critical paths | 🔵 Weekly |

### 3.3 Test Quality Rules
- **No hand-built literals** → Use factories/fixtures
- **No wall-clock time, network, global state** → Deterministic
- **Mock at boundaries** (external APIs, DB), not internals
- **Flaky tests** → Quarantine → Fix within 1 sprint
- **Test names**: `test_<what>_<condition>_<expected>`

---

## 4. Git & Version Control (Enforced by CI)

### 4.1 Commit Convention (Enforced by `commitlint`)
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

### 4.2 Branch Strategy
```
main (protected)
  ├── feature/*     → PR → CI → review → squash merge
  ├── fix/*         → PR → CI → review → squash merge
  ├── chore/*       → PR → CI → auto-merge (if green)
  ├── docs/*        → PR → CI → auto-merge (if green)
  └── release/*     → PR → CI → tag → deploy
```

### 4.3 Branch Protection
**NOT available on this repository.** `GET /repos/Er-Sajan-PLG/JARVIS/branches/main/protection`
returns **HTTP 403** ("Upgrade to GitHub Pro or make this repository public"), so
none of the following are enforced by GitHub. They hold as *convention* only:
- Required PR from a feature branch — **convention** (a direct push to `main` is not blocked)
- Required CI passes — **published as commit statuses, cannot block merge** (RISK-012)
- 1 approval — **0 for solo repo** (GitHub forbids self-approval)
- No force push / linear history — **convention** (squash merge is the practice)
- Signed commits — **not enforced**; commits report `N`/`E` (RISK-011)

Enforcement is *process, not policy*: the gate publishes statuses, the pipeline
stops on red, and a human does not press merge. See `docs/ACCEPTED_RISKS.md`
(RISK-012, RISK-011) and `docs/adr/ADR-013-jarvis-orchestrates-n8n-executes.md`.

### 4.4 Versioning
- **Scheme**: Semantic Versioning (MAJOR.MINOR.PATCH)
- **Source**: **git tags** — the version is *derived* from them at import time
  (see `app/config/version.py` and `docs/VERSIONING.md`).
- **Release**: Tag `vX.Y.Z` is the version bump
- **Bump Script**: `scripts/bump_version.py [patch|minor|major]` (tags first;
  `pyproject.toml` is metadata, not the authority)

---

## 5. Architecture Decision Records (ADRs)

### 5.1 When to Create ADR
- New architectural pattern
- Breaking change to module boundaries
- New external dependency (esp. ML/infra)
- Change to core data models
- New external integration

### 5.2 ADR Template
```markdown
# ADR-XXX: <Title>

**Date**: YYYY-MM-DD
**Author**: <name>

## Context
What problem are we solving?

## Decision
What did we decide?

## Consequences
### Positive
- ...

### Negative
- ...

## Migration Plan (if breaking)
- Step 1: ...
- Step 2: ...
```

### 5.3 ADR Index (docs/adr/)
| ADR | Title | Status |
|-----|-------|--------|
| ADR-006 | Pragmatic Hybrid Architecture | ✅ Accepted |
| ADR-007 | Domain Purity & Dataclasses | ✅ Accepted |
| ADR-008 | Tiered Tool Safety Policy | ✅ Accepted |
| ADR-009 | Multi-Provider Circuit Breaker | ✅ Accepted |
| ADR-010 | Adapters & Integrations Isolation | ✅ Accepted |

---

## 6. Governance for Agent Work

### 6.1 Agent Instructions (This File)
**Every agent MUST:**
1. Read this file first
2. Follow all standards in Sections 2-5
3. Run governance check: `.venv/bin/python scripts/board/review.py`
4. Run tests: `.venv/bin/pytest tests/ -q`
5. Run lint/typecheck: `.venv/bin/ruff check app/ && .venv/bin/mypy --strict app/`

### 6.2 Agent Workflow Enforcement
- **No direct commits to main** → Always PR
- **No skipping CI** → All 6 jobs must pass
- **No large commits** → One logical change per commit
- **No undocumented changes** → Docs updated in same PR
- **No untested code** → Test written first

### 6.3 Agent Self-Check (Before Every Commit)
```bash
# Run this before committing
.venv/bin/ruff check app/ tests/
.venv/bin/ruff format --check app/ tests/
.venv/bin/mypy --strict app/
.venv/bin/pytest tests/ -q
.venv/bin/python scripts/board/review.py
```

---

## 7. Modularity & Isolation Verification

### 7.1 Current Module Boundaries
| Module | Responsibility | Deps | Isolated? |
|--------|----------------|------|-----------|
| `app.domain` | Pure dataclasses | stdlib only | ✅ |
| `app.brain` | Intent→Plan→Execute→Synthesize | domain, events, guardrails | ✅ |
| `app.adapters` | HTTP/WS + Auth | bootstrap, brain | ✅ |
| `app.models` | Provider routing + circuit breakers | resources | ✅ |
| `app.memory` | Hybrid BM25+Chroma | integrations | ✅ |
| `app.guardrails` | @safety_gate decorator | standalone | ✅ |
| `app.events` | InMemoryAsyncBus | standalone | ✅ |
| `app.resources` | Token budget, rate limits, health | standalone | ✅ |
| `app.memory.integrations` | ChromaDB, OCR | wrapped | ✅ |

### 7.2 Isolation Gaps (Tracked)
| Gap | ADR | Sprint |
|-----|-----|--------|
| MCP components missing | ADR-010 | Sprint 3 |
| LangGraph checkpointing | ADR-006 | Sprint 3 |
| OTel semantic conventions | ADR-006 | Sprint 3 |
| @safety_gate on all tools | ADR-008 | Sprint 3 |

---

## 8. Debugging & Logging Standards

### 8.1 Structured Logging
```python
# Format: JSON with correlation_id
{"timestamp": "2026-09-10T10:30:00", "level": "INFO", "logger": "app.main", "correlation_id": "abc-123", "message": "Request processed"}
```

### 8.2 Correlation IDs
- Every request: `X-Correlation-ID` header (auto-generated if missing)
- Propagated through all async calls
- Included in all log entries

### 8.3 Debugging Checklist
- [ ] Structured logs with correlation IDs
- [ ] Metrics exposed at `/metrics` (Prometheus)
- [ ] Health check at `/health` (liveness)
- [ ] Readiness check at `/ready` (readiness)
- [ ] Correlation ID propagated in all async calls
- [ ] Errors include correlation ID for tracing

---

## 9. Documentation Standards

### 9.1 Required Docs Per Module
| Doc | Location | Updated When |
|-----|----------|--------------|
| Architecture | `docs/ARCHITECTURE.md` | Architecture change |
| API Contract | `docs/API_CONTRACT.md` | API change |
| Governance | `docs/GOVERNANCE.md` | Process change |
| Roadmap | `docs/ROADMAP.md` | Sprint planning |
| Development | `docs/DEVELOPMENT.md` | Tooling change |
| Capability Tracker | `docs/CAPABILITY_TRACKER.md` | Contract milestone |

### 9.2 Doc Update Rule
**Every PR that changes behavior MUST update relevant docs in same PR.**
No separate "docs later" PRs.

### 9.3 Mandatory: read the doc-type contract BEFORE writing any document

**This is a blocking gate, for agents and humans alike. Do not write or edit any
document without passing through it.**

Before creating or editing a file under `docs/` (or any root `*.md`):

1. **Read `docs/DOC-GOVERNANCE.md` §10.** It states, per document type, what a
   correct document looks like and which drift trap that type falls into. If you
   have not read it in this session, read it now.
2. **Declare the type.** Every document carries `**Type**: <name>` immediately
   under `**Status**`. Types: `architecture`, `reference`, `governance`, `adr`,
   `runbook`, `guide`, `roadmap`, `register`, `generated`, `changelog`, `index`,
   `policy`, `snapshot`. If you cannot name the type, you do not yet know what you
   are writing — stop and decide.
3. **Scaffold, do not hand-write the header:**

   ```bash
   .venv/bin/python scripts/new_doc.py <type> docs/<path>.md \
       --title "<Title>" --source "<the code this describes>"
   ```

4. **Fill it against the code, not from memory.** Open the file named in
   `**Source**` while you write. Writing from memory is the most common origin of
   drift.
5. **Verify:** `.venv/bin/python scripts/check_docs.py --strict`

**Why this is a gate and not advice.** The type contract is enforced by
`scripts/check_docs.py` (rule 10), by `githooks/pre-commit`, and by the `gate_docs`
CI check. A document that declares no type, or violates its type, is rejected. An
agent that writes documentation without passing through this section is producing
a file the gate will refuse — and, worse, one no reader can tell is current.

**The load-bearing rule for every type:** an ACTIVE document that describes code
**must** carry `**Source**` naming it. That binding is what turns a future code
change into a present gate failure — move the code and the document goes red,
instead of going quietly stale.

---

## 10. Compliance Checklist (Run Before Commit)

```bash
# Quick compliance check
.venv/bin/ruff check app/ tests/
.venv/bin/ruff format --check app/ tests/
.venv/bin/mypy --strict app/
.venv/bin/pytest tests/ -q
.venv/bin/python scripts/board/review.py
.venv/bin/python scripts/check_docs.py --strict   # doc structure + type contract
.venv/bin/python scripts/doc_type_table.py --check # documented contract == code
```

**All must pass = compliant. Any failure = fix before commit.**

---

## 11. Enforcement & Escalation

| Violation | Consequence |
|-----------|-------------|
| Commit to main without PR | Revert immediately |
| CI failing but merged | Revert + process review |
| Large commit (>500 lines) | Split required |
| No tests for new code | Revert + write tests |
| Docs not updated | PR blocked until updated |
| Architecture boundary violation | ADR required before merge |

---

**This document is the single source of truth for all agent work on JARVIS.**
Any deviation requires Architecture Review Board approval.
