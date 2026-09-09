# JARVIS Roadmap — Living Document v3.0.0

**Status**: ACTIVE — Prioritized from forensic audit findings  
**Source**: Forensic Architecture Audit (2026-09-10) + USAT Audit  
**Workflow Orchestration**: n8n (all CI/CD, automation, approval flows)  
**Last Updated**: 2026-09-10

---

## 1. Roadmap Principles

1. **Unblock v3.0 First** — The architecture is implemented; only operational blockers remain
2. **Archive, Don't Migrate** — Legacy v2.x servers are dead code; archive them
3. **n8n Owns Automation** — No GitHub Actions for business logic
4. **Python 3.11/3.12 Only** — 3.14 breaks ML ecosystem
5. **Capability Contract Drives Features** — JARVIS must match PROFESSOR-J interface

---

## 2. Sprint 0 — UNBLOCK (Week 0, Days 1-2)

**Goal**: Working v3.0 runtime in < 2 hours

| Task | Owner | n8n Workflow | Status |
|------|-------|--------------|--------|
| Recreate venv with Python 3.11 | Dev | `JARVIS-Setup-Env` | 🔴 TODO |
| Install deps (`pip install -r requirements.txt`) | Dev | `JARVIS-Setup-Env` | 🔴 TODO |
| Add `JARVIS_API_KEY` to `.env` | Dev | `JARVIS-Setup-Secrets` | 🔴 TODO |
| Archive legacy servers (`app/api/server.py`, `app/web_api_server.py` → `app/legacy/`) | Dev | `JARVIS-Archive-Legacy` | 🔴 TODO |
| Add WS auth (`validate_api_key` to `ws_router`) | Dev | `JARVIS-Fix-WS-Auth` | 🔴 TODO |
| Verify: `.venv/bin/python -m app.main` | Dev | `JARVIS-Smoke-Test` | 🔴 TODO |

**Exit Criteria**: v3.0 server starts, health endpoint returns 200, chat completion works via REST + WS

---

## 3. Sprint 1 — FOUNDATION (Week 1-2)

**Goal**: Production-grade foundations, security, CI/CD

| Task | Owner | n8n Workflow | Status |
|------|-------|--------------|--------|
| **CI Pipeline** | | | |
| Create `JARVIS-CI` workflow (lint → typecheck → test → build → security) | Dev | n8n | 🔴 TODO |
| Configure branch protection via GitHub API | Dev | `JARVIS-Branch-Protection` | 🔴 TODO |
| Enable Dependabot (grouped PRs, weekly) | Dev | `JARVIS-Dependabot` | 🔴 TODO |
| **Security** | | | |
| Add `SECURITY.md` with disclosure email | Dev | — | 🔴 TODO |
| Add `.gitleaks.toml` + pre-commit hook | Dev | `JARVIS-Precommit` | 🔴 TODO |
| Add CodeQL SAST workflow | Dev | `JARVIS-Security` | 🔴 TODO |
| Add container scan (Trivy) | Dev | `JARVIS-Security` | 🔴 TODO |
| **Code Quality** | | | |
| Fix bare `except` in `app/conversation/manager.py:203`, `app/memory/store.py:210` | Dev | — | 🔴 TODO |
| Fix mutable defaults in archived legacy (for hygiene) | Dev | — | 🔴 TODO |
| Add `ruff` + `mypy` to pre-commit + CI | Dev | `JARVIS-Precommit` | 🔴 TODO |
| Pin Python 3.11 in `pyproject.toml` + CI | Dev | — | 🔴 TODO |
| **Documentation** | | | |
| Add `LICENSE` (MIT) | Dev | — | 🔴 TODO |
| Add `.env.example` documenting all 26+ keys | Dev | — | 🔴 TODO |

**Exit Criteria**: CI runs on every PR, blocks merge on failure; security scans pass; code quality gates enforced

---

## 4. Sprint 2 — HARDENING (Week 3-4)

**Goal**: Containerization, observability, release automation

| Task | Owner | n8n Workflow | Status |
|------|-------|--------------|--------|
| **Containerization** | | | |
| Create multi-stage `Dockerfile` (non-root user, healthcheck) | Dev | `JARVIS-Docker-Build` | 🔴 TODO |
| Add `.dockerignore` | Dev | — | 🔴 TODO |
| Update `docker-compose.yml` for app service | Dev | `JARVIS-Docker-Build` | 🔴 TODO |
| **Observability** | | | |
| Add structured logging (JSON, correlation IDs) | Dev | — | 🔴 TODO |
| Add `/health` and `/ready` endpoints (unauthenticated, minimal) | Dev | — | 🔴 TODO |
| Add metrics endpoint (Prometheus format) | Dev | — | 🔴 TODO |
| **Release Automation** | | | |
| Create `JARVIS-Release` workflow (semantic-release) | Dev | n8n | 🔴 TODO |
| Configure conventional commits enforcement | Dev | `JARVIS-CI` | 🔴 TODO |
| Add SBOM generation (CycloneDX) | Dev | `JARVIS-Release` | 🔴 TODO |
| **Testing** | | | |
| Achieve 80% coverage threshold | Dev | `JARVIS-CI` | 🔴 TODO |
| Add integration tests for critical paths | Dev | `JARVIS-CI` | 🔴 TODO |

**Exit Criteria**: Docker image builds, deploys to staging; release automation works; 80% coverage

---

## 5. Sprint 3 — CAPABILITY CONTRACT ALIGNMENT (Week 5-8)

**Goal**: Match PROFESSOR-J Capability Contract v1.0

| Capability | Current | Target | Tasks | Status |
|------------|---------|--------|-------|--------|
| **Cognitive Engine (LangGraph)** | Direct async loop | LangGraph orchestration | Port from PROFESSOR-J ADR-003; replace `app/brain/` loop | 🔴 TODO |
| **Memory (rich schema)** | Hybrid BM25+Chroma | 4-stage pipeline + rich schema | Add `MemoryItem` schema (fact/episode/procedure/preference/conversation); add extraction + deduplication | 🔴 TODO |
| **MCP Client** | None | stdio + Streamable HTTP | Port from PROFESSOR-J PR #86; add to `app/integrations/mcp/` | 🔴 TODO |
| **Eval Suite** | None | Regression suite | Add `evals/` package; CI integration | 🔴 TODO |
| **Session/Checkpoint** | Basic | LangGraph `MemorySaver`/`PostgresCheckpointer` | Upgrade `app/session/` | 🟡 PARTIAL |

**Tracking**: See `CAPABILITY_TRACKER.md` for detailed milestones

---

## 6. Sprint 4 — ECOSYSTEM INTEGRATION (Week 9-12)

**Goal**: Full STEMMA/LearningHub/PROFESSOR-J ecosystem integration

| Integration | Target | Status |
|-------------|--------|--------|
| **STEMMA (canonical foundation)** | LHS adapter, curriculum grounding | 🔴 TODO |
| **LearningHub (app)** | SSO, shared session, API gateway | 🔴 TODO |
| **PROFESSOR-J (agent)** | MCP server, capability contract sync | 🔴 TODO |
| **Cloudflare Pages Deploy** | Auto-deploy on tag | 🔴 TODO |

---

## 7. Technical Debt Register (Active)

| ID | Item | Severity | Sprint | Owner |
|----|------|----------|--------|-------|
| TD-001 | Python 3.14 venv (recreate with 3.11) | 🔴 CRITICAL | 0 | Dev |
| TD-002 | Legacy servers in namespace (archive) | 🔴 CRITICAL | 0 | Dev |
| TD-003 | Missing `JARVIS_API_KEY` | 🔴 CRITICAL | 0 | Dev |
| TD-004 | WS auth bypass | 🔴 CRITICAL | 0 | Dev |
| TD-005 | No CI pipeline | 🔴 CRITICAL | 1 | Dev |
| TD-006 | No branch protection | 🔴 CRITICAL | 1 | Dev |
| TD-007 | No security scanning | 🟠 HIGH | 1 | Dev |
| TD-008 | No container image | 🟠 HIGH | 2 | Dev |
| TD-009 | No release automation | 🟠 HIGH | 2 | Dev |
| TD-010 | Capability Contract gaps | 🟡 MEDIUM | 3 | Dev |
| TD-011 | No eval suite | 🟡 MEDIUM | 3 | Dev |
| TD-012 | No Dockerfile | 🟠 HIGH | 2 | Dev |

---

## 8. Milestone Timeline

```
Week 0:     ████████████████████████████████████  Sprint 0: UNBLOCK
Week 1-2:   ████████████████████████████████████  Sprint 1: FOUNDATION
Week 3-4:   ████████████████████████████████████  Sprint 2: HARDENING
Week 5-8:   ████████████████████████████████████  Sprint 3: CAPABILITY CONTRACT
Week 9-12:  ████████████████████████████████████  Sprint 4: ECOSYSTEM
```

---

## 9. Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| **Time to working dev env** | Broken | < 5 min | `JARVIS-Setup-Env` workflow |
| **CI pass rate** | 0% | 100% | n8n `JARVIS-CI` |
| **Test coverage** | Unknown | ≥ 80% | pytest --cov |
| **Security scan pass** | None | 100% | CodeQL + gitleaks + Trivy |
| **Deploy frequency** | Manual | On every tag | n8n `JARVIS-Release` |
| **Capability Contract compliance** | ~40% | 100% | `CAPABILITY_TRACKER.md` |
| **MTTR (Mean Time to Recovery)** | Unknown | < 30 min | n8n incident workflows |

---

## 10. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Python 3.14 breaks deps | High | Critical | Recreate venv with 3.11 immediately |
| Legacy servers cause confusion | High | Medium | Archive in Sprint 0 |
| Capability Contract drift | Medium | High | Quarterly sync with PROFESSOR-J |
| n8n workflow complexity | Medium | Medium | Version control workflows; document |
| Single-tenant auth scaling | Low | Medium | Design for multi-tenant if needed |

---

## 11. Decision Log (Roadmap Changes)

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-10 | Archive legacy servers, don't migrate | Forensic audit: v3.0 clean, v2.x dead code |
| 2026-09-10 | n8n owns all automation | User requirement; separation of concerns |
| 2026-09-10 | Python 3.11/3.12 only | 3.14 incompatible with ML ecosystem |
| 2026-09-10 | Capability Contract drives features | JARVIS ↔ PROFESSOR-J parity required |

---

**Next**: See `DEVELOPMENT.md` for daily workflow, `API_CONTRACT.md` for API surface, `CAPABILITY_TRACKER.md` for contract compliance.