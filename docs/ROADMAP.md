# JARVIS Roadmap

**Status**: ACTIVE
**Type**: roadmap
**Last Updated**: 2026-09-13

**Workflow Orchestration**: n8n (all CI/CD, automation, approval flows)

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
| Recreate venv with Python 3.11 | Dev | — | ✅ DONE |
| Install deps (`pip install -r requirements.txt`) | Dev | — | ✅ DONE |
| Add `JARVIS_API_KEY` to `.env` | Dev | — | ✅ DONE |
| Archive legacy servers (moved to `legacy/`, not `app/legacy/`) | Dev | — | ✅ DONE |
| Add WS auth (`validate_api_key` to `ws_router`) | Dev | — | ✅ DONE (the 2026-09-10 claim was false: `ws_router` had no check until `app/adapters/security.py`, 2026-09-12; `tests/unit/test_ws_sse_auth.py` now pins it) |
| Verify: `.venv/bin/python -m app.main` | Dev | — | ✅ DONE |

> **Completed.** Every Sprint 0 task is done. Two corrections to the plan as written:
> the archived servers live at `legacy/` (not `app/legacy/`), and none of these needed
> an n8n workflow — they were one-off shell actions, so the `JARVIS-Setup-Env` /
> `JARVIS-Archive-Legacy` workflows named here were never built and should not be
> looked for in the n8n instance.

**Exit Criteria**: v3.0 server starts, health endpoint returns 200, chat completion works via REST + WS

---

## 3. Sprint 1 — FOUNDATION (Week 1-2)

**Goal**: Production-grade foundations, security, CI/CD

| Task | Owner | n8n Workflow | Status |
|------|-------|--------------|--------|
| **CI Pipeline** | | | |
|| Create the local CI plane (`JARVIS-CI-Local` -> `scripts/ci_bridge.py` -> `scripts/ci_gate.py`) | Dev | `JARVIS-CI-Local` | ✅ VERIFIED (<!--fact:gate_count-->26<!--/fact--> gates; <!--fact:context_count-->9<!--/fact-->/<!--fact:context_count-->9<!--/fact--> contexts published; Actions billing-blocked) ||
|| Configure branch protection via GitHub API | Dev | *(GitHub API — 403)* | ⛔ BLOCKED (GitHub 403 free-tier repo; RISK-012; `.github/workflows/release.yml` exists as dispatch fallback) ||
|| Enable Dependabot (grouped PRs, weekly) | Dev | *(GitHub, no n8n workflow)* | ✅ VERIFIED (.github/dependabot.yml; PR #23-#36 merged via SSH) ||
| **Security** | | | |
|| Add `SECURITY.md` with disclosure email | Dev | — | ✅ VERIFIED (SECURITY.md present) ||
|| Add `.gitleaks.toml` + pre-commit hook | Dev | *(pre-commit hook)* | ✅ VERIFIED (.pre-commit-config.yaml + ruff/mypy/gitleaks; gate passes) ||
|| Add CodeQL SAST workflow | Dev | *(local: `codeql` CLI, no Actions)* | 🟡 PARTIAL — the *workflow* is genuinely impossible (Actions billing-blocked), but CodeQL is **not** unavailable: the CLI (`github/codeql-cli-binaries` v2.27.0, 410 MB linux64) runs standalone without Actions and could join the gate. Today the gate covers SAST with semgrep + bandit + trufflehog + gitleaks, so the gap is depth (dataflow), not absence. Tracked as an improvement, not a blocker ||
|| Add container scan (Trivy) | Dev | *(in `ci_gate.py`)* | ✅ VERIFIED (Trivy fs gate in 22-check CI pipeline; Dockerfile + .dockerignore + hadolint) ||
| **Code Quality** | | | |
|| Fix bare `except` in `app/conversation/manager.py:203`, `app/memory/store.py:210` | Dev | — | ✅ VERIFIED (grep: 0 bare `except:` hits in `app/`) ||
|| Fix mutable defaults in archived legacy (for hygiene) | Dev | — | 🟡 PARTIAL (legacy moved to `legacy/`; hygiene enforced by ruff gate) ||
|| Add `ruff` + `mypy` to pre-commit + CI | Dev | *(pre-commit hook)* | ✅ VERIFIED (.pre-commit-config.yaml: ruff + mypy; `.governance/mypy_baseline.txt`=494; `--disable-error-code=misc` for FastAPI decorator noise) ||
|| Pin Python 3.11 in `pyproject.toml` + CI | Dev | — | ✅ VERIFIED (pyproject.toml: `>=3.11`; `.venv`: cpython 3.11.16) ||
| **Documentation** | | | |
|| Add `LICENSE` (MIT) | Dev | — | ✅ VERIFIED (LICENSE present) ||
|| Add `.env.example` documenting all 26+ keys | Dev | — | ✅ VERIFIED (.env.example present; 26+ keys) ||

**Exit Criteria**: CI runs on every PR, blocks merge on failure; security scans pass; code quality gates enforced

---

## 4. Sprint 2 — HARDENING (Week 3-4)

**Goal**: Containerization, observability, release automation

| Task | Owner | n8n Workflow | Status |
|------|-------|--------------|--------|
| **Containerization** | | | |
| Create multi-stage `Dockerfile` (non-root user, healthcheck) | Dev | *(no workflow — plain `docker build`)* | ✅ VERIFIED (Dockerfile + .dockerignore present; multi-stage build structure verified) |
| Add `.dockerignore` | Dev | — | ✅ VERIFIED (.dockerignore present) |
| Update `docker-compose.yml` for app service | Dev | *(no workflow — plain `docker compose`)* | ✅ VERIFIED (docker-compose.yml present) |
| **Observability** | | | |
| Add structured logging (JSON, correlation IDs) | Dev | — | 🟡 PARTIAL (middleware in `app/main.py` has correlation IDs; full structured JSON logging via `app/telemetry/` pending — Sprint 3/OTel gap) |
| Add `/health` and `/ready` endpoints (unauthenticated, minimal) | Dev | — | ✅ VERIFIED (`app/adapters/http/router.py`: `/health`; `app/main.py`: `/ready` + `/metrics`) |
| Add metrics endpoint (Prometheus format) | Dev | — | ✅ VERIFIED (`/metrics` endpoint + `metrics.export_prometheus()` reference in main.py) |
| **Release Automation** | | | |
| Create release automation (semantic-release) | Dev | *(local: `scripts/version_bump.py` + `scripts/publish_release.py`)* | ✅ VERIFIED — **release publishing works locally without Actions.** Tags: `githooks/pre-push` auto-tags from conventional commits. Releases: `scripts/publish_release.py` publishes via `gh` (the CI token lacks `contents:write`; `gh`'s repo-scoped classic token can). 2026-09-13: backfilled so **21 tags → 21 GitHub releases** (was 21 tags / **0 releases** — notes, compare links and "Latest" never existed). Wired into the hook so it stays automatic. Actions `release.yml` remains dispatch-only, which no longer blocks anything (TD-009 closed) |
| Configure conventional commits enforcement | Dev | *(pre-commit hook)* | 🟡 PARTIAL (`.pre-commit-config.yaml`: `commitlint` v9.26.0 + conventional config; `scripts/commit.sh` handles two-pass commit; enforcement is pre-commit layer, verified working — no separate GitHub Actions check due to Actions block) |
| Add SBOM generation (CycloneDX) | Dev | *(in `ci_gate.py`)* | ✅ VERIFIED — **not missing.** `gate_sbom` produces a real CycloneDX 1.7 SBOM (`artifacts/sbom-<sha>.cdx.json`, 172 components); **57 artifacts** exist on disk and `syft` is installed. RISK-003 was already closed 2026-09-10; this row's ❌ was a doc lag |
| **Testing** | | | |
| Achieve 80% coverage threshold | Dev | *(in `ci_gate.py`)* | ✅ VERIFIED — **<!--fact:coverage-->96<!--/fact-->%** measured (`pytest tests/ -q --cov=app --cov-report=term`), <!--fact:test_count-->1240<!--/fact--> passed; floor 80% exceeded. RISK-004's "~36%" figure was stale and has been corrected |
| Add integration tests for critical paths | Dev | *(in `ci_gate.py`)* | ✅ VERIFIED — `tests/integration/test_ci_bridge_gate_loop.py` (12 tests, 2026-09-13) pins the CI-bridge → `ci_gate` → status-publish contract: blocking failures redden their context, reported-only failures (mypy/RISK-005, coverage/RISK-004) stay green but visible in the description, every gate maps to a published context, a 403'd publish is reported as `publish-failed` rather than announced as success, gate JSON is parsed, and bridge state round-trips + degrades on corruption. Mutation-checked: reverting the reported-only rule fails 2 of them. `tests/e2e/` remains empty (no live-instance DAST — that is RISK-006, still open) |

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
| TD-001 | Python 3.14 venv (recreate with 3.11) | ✅ RESOLVED | 0 | Dev |
| TD-002 | Legacy servers in namespace (archive) | ✅ RESOLVED — moved to `legacy/` | 0 | Dev |
| TD-003 | Missing `JARVIS_API_KEY` | ✅ RESOLVED | 0 | Dev |
| TD-004 | WS auth bypass | ✅ RESOLVED | 0 | Dev |
| TD-005 | No CI pipeline | ✅ RESOLVED — local n8n plane, <!--fact:gate_count-->26<!--/fact--> checks, <!--fact:context_count-->9<!--/fact--> published contexts (Actions billing-blocked) | 1 | Dev |
| TD-006 | No branch protection | ⛔ BLOCKED — GitHub returns 403 on a private free-tier repo (RISK-012) | 1 | Dev |
| TD-007 | No security scanning | ✅ RESOLVED — gitleaks, trufflehog, bandit, semgrep, trivy, osv, pip-audit in the gate | 1 | Dev |
| TD-008 | No container image | ✅ RESOLVED — multi-stage Dockerfile + hadolint gate | 2 | Dev |
| TD-009 | No release automation | ✅ RESOLVED — tags auto-cut by `githooks/pre-push`; releases published by `scripts/publish_release.py` via `gh` (Actions-independent). 21 tags → 21 releases as of 2026-09-13 | 2 | Dev |
| TD-010 | Capability Contract gaps | 🟡 MEDIUM — see `CAPABILITY_TRACKER.md` | 3 | Dev |
| TD-011 | No eval suite | 🟡 MEDIUM | 3 | Dev |
| TD-012 | No Dockerfile | ✅ RESOLVED — same as TD-008 | 2 | Dev |

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
| **Time to working dev env** | Working | < 5 min | `scripts/setup_dev_env.sh` (no `JARVIS-Setup-Env` workflow exists) |
| **CI pass rate** | 100% on gated PRs | 100% | `scripts/ci_gate.py` via `JARVIS-CI-Local` |
| **Test coverage** | Unknown | ≥ 80% | pytest --cov |
| **Security scan pass** | None | 100% | CodeQL + gitleaks + Trivy |
| **Deploy frequency** | Manual | On every tag | *(no deploy automation — see TD-009)* |
| **Capability Contract compliance** | ~40% | 100% | `CAPABILITY_TRACKER.md` |
| **MTTR (Mean Time to Recovery)** | Unknown | < 30 min | *(manual; no incident workflow exists)* |

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
