# Documentation Audit Report — JARVIS

**Status**: ACTIVE
**Type**: snapshot
**Last Updated**: 2026-09-26
**Reviewed**: 2026-09-26
**Source**: repo-wide inspection at `1f25e3b` (see report §1)

**Date**: 2026-09-26 · **HEAD**: `1f25e3b` · **Auditor**: autonomous docs agent (read-only phase; no files modified to produce this)
**Scope**: every human-readable artifact repo-wide (105 `*.md`, 0 `.rst`/`.adoc`, policies, contracts, prompts, diagrams, CLI help, CI comments, badges), plus all existing doc automation, hooks, and CI.

---

## 1. Inventory (condensed)

105 first-party markdown files: 78 under `docs/` (<!--fact:adr_count-->19<!--/fact--> ADRs, 10 architecture, 6 archive, 2 migrations, 2 timelines, 14 modules, 27 top-level + index), 6 root (`README, AGENTS, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, DEVLOG`), plus `n8n/README.md`, `tgcall/README.md`, 4 `prompts/*.md`, submodule/artifact strays. Zero `app/*/README.md` (0/29 packages), zero `frontend/`/`mobile/` docs, no `mkdocs/docusaurus/Sphinx`, no OpenAPI/GraphQL/protobuf files, 9 Mermaid blocks (6 architecture docs + `ARCHITECTURE.md`×2 + timeline) with zero rendered PNGs, 18 argparse-based `scripts/*.py` CLIs with no generated CLI reference, no Alembic/SQL migration chain (`app/db/` empty).

**Orphans**: 27 files linked only at directory granularity (`architecture/`×10, `archive/`×6, `migrations/`×2, `timelines/`×2, legacy `modules/`×7); unindexed: `tgcall/README.md`, `n8n/README.md`, `prompts/*.md`×4, `.archaeology/`, `.hermes/plans/`, `data/uploads/*.md`. **Undocumented surface**: 11 `app/` packages with no module page (`backend, conversation, core, evals, events, modes, prompt, resources, security, utils, workspace`) plus `api, mcp` (partial) and all of `frontend/`, `mobile/`, `n8n/`.

## 2. Staleness findings (doc → status → evidence)

| Document | Status | Evidence |
|---|---|---|
| `README.md` | **Stale (Critical)** | Version `v3.22.1+dev` (:28) vs tag `v3.34.2`; ADRs `15` (:175) vs 17 files; risks `16` (:176) vs 23 `RISK-*`; CI-gate heading two behind the `def gate_*` count at audit time (:116); governance table claims `Doc Drift ✅` (:162–173) while drift exists |
| `docs/TOOLS.md` | **Stale (High)** | `15 entries` (:63) / `14 entries: 5+3+6` (:67–68) vs 16 (17 with `JARVIS_WEB_SEARCH=1`); omits `spawn_worker`, `web_search`; header 2026-09-18 vs `app/tools` 2026-09-26 |
| `docs/ARCHITECTURE.md` | **Stale (High)** | 2026-09-18 vs `app/bootstrap.py`/`app/brain`/`app/main.py` 2026-09-26; misses migration Steps 0–4; `analyze(prompt)` (:139,230) vs `analyze(self, query, has_attachments=False)` + new fields |
| `docs/ROADMAP.md` | **Stale (Medium)** | Declares sprints complete at `v3.23.0` (:234) vs HEAD `v3.34.2`; no sprint covers v3.25→v3.34 / migration |
| `docs/DATABASE.md` | **Stale (Medium)** | 2026-09-14 vs `app/memory` 2026-09-17; `JARVIS_DATABASE_URL` row points at empty `app/db/` (real reader `app/bootstrap.py:97`) |
| `docs/API_CONTRACT.md` | **Stale (Low)** | 2026-09-19; `app/main.py` moved 2026-09-26 (CORS origin, Telegram gating, bind) |
| `docs/DEVELOPMENT.md` | **Broken (Medium)** | `from app.adapters import http_router` (:298) — no such export; stale test pointers; header 2026-09-13 vs commit 2026-09-18 |
| `docs/CAPABILITY_TRACKER.md` | **Stale (Low)** | Misses `spawn_worker` + `web_search` |
| Dead refs | **Broken (High)** | `AGENTS.md:201-202,273-274,366`, `docs/TOOLS.md:234`, `docs/AGENTS.md` cite `CHANGELOG_recovered.md`, `DEVLOG_recovered.md`, `V3_ROADMAP.md`, `CHANGELOG.md` — all absent on disk (only root `DEVLOG.md` exists) |
| Dead external links | **Broken (Medium)** | `scripts/check_links.py`: `github.com/Er-Sajan-PLG/JARVIS` 404 (`docs/GITHUB-APP-SETUP.md:47`), `.../Universal_Software_Auditor` 404 (`docs/GOVERNANCE.md:9`) |
| Header dates | **Stale (Low)** | `Last Updated` headers predate last commits: `MEMORY.md` (09-13 vs 09-19), `GOVERNANCE.md` (09-14 vs 09-26), `DEVELOPMENT.md`, `DATABASE.md`, `CI-GATE-SOTA.md`, root `AGENTS.md` |
| `docs/CONFIG.md` | **OK (fresh)** | 2026-09-26, enumerates `JARVIS_AUDIT_SINK`, `JARVIS_WEB_SEARCH`; minor: “no reader” wording overstates for registry-driven providers; 3 code-only vars (`HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, `TELEGRAM_API_KEYS`) |
| `docs/VOICE.md`, `docs/CI-GATE-SOTA.md`, `docs/FINAL_STATE.md` | **OK / pinned** | Fresh or correctly labeled snapshot; `CI-GATE-SOTA` gate total behind HEAD is a known pending sync |

## 3. Existing automation audit

| Capability | Exists? | Pre-commit? | Pre-push/CI? | Gap |
|---|---|---|---|---|
| Markdown lint/style/spellcheck | ❌ No (no markdownlint/vale/codespell anywhere) | — | — | **Missing** |
| Docstring coverage minimum | ❌ No (no interrogate/docstr-coverage) | — | — | **Missing** |
| Code→doc co-change detection (Layer 1) | ❌ No | — | — | **Missing — pre-commit has zero doc hooks** |
| Internal link check | Partial (`check_links.py` = external only) | ❌ | ❌ (script exists, unwired) | Unwired |
| External link check | ✅ `check_links.py` (2 dead found) | — | Scheduled only | Not on PR path |
| Path-claim check | ✅ `check_docs.py::check_paths` | ❌ | ✅ pre-push + unit tests | — |
| Header/type/contract checks | ✅ `check_docs.py` (10 rules) | ❌ | ✅ pre-push + unit tests | — |
| Module/route/env census | ✅ `check_doc_coverage.py` + unit tests | ❌ | ✅ pre-push | — |
| Machine-fact sync | ✅ `sync_doc_facts.py` + pre-commit auto-sync + `.governance/doc_facts.json` | ✅ (auto) | ✅ | Counts only; prose untouched |
| Semantic-review cadence | ✅ `doc_review_due.py` (git-history cadence) | — | Scheduled only | No PR trigger |
| Scheduled sweep + auto-issue | ✅ `scheduled_doc_maintenance.py` (15-day) + `n8n-workflows/doc-maintenance.json` (cron) | — | ✅ scheduled | Exists; verify cron live |
| Doc scaffolding | ✅ `scripts/new_doc.py` (type contract) | n/a | ✅ (gate rejects unscaffolded) | — |
| Mermaid regeneration | Partial (`update_architecture_docs.py` embeds templates; no verified wiring/schedule) | ❌ | UNKNOWN — needs human review | Unverified |
| Snippet execution/compile check | ❌ No | — | — | **Missing** |
| OpenAPI generation | ❌ (hand-written `API_CONTRACT.md` + FastAPI runtime docs; route census mitigates) | — | — | Accepted risk, not gap |
| Doc-to-code manifest | ❌ No manifest file (`**Source**` bindings + `docs/metadata/*_graph.json` are partial equivalents) | — | — | **Missing** |
| Conventional-commit lint | ✅ commitlint (pre-commit + CI job, currently passing) | ✅ | ✅ | — |
| Secret scanning | ✅ gitleaks (pre-commit + pre-push + CI job) | ✅ | ✅ | — |
| CODEOWNERS doc review | Partial (single owner, core paths only, nothing doc-specific) | n/a | n/a | No docs ownership |
| Required status checks | ❌ Impossible (private-free repo, no branch protection; RISK-012) | n/a | n/a | **Structural: hooks + local n8n plane are the only backstop** |
| CI system | ⚠️ GitHub Actions **billing-disabled** (`workflow_dispatch` only); real CI = local n8n (30-min) + `ci_gate.py` (gate suite) + `ci_bridge.py` | n/a | ✅ local | Any new check must land in `ci_gate.py`, not Actions yaml |

**Sync mechanism audit**: today only machine-derivable facts sync (`sync_doc_facts.py`: counts/versions/paths). Nothing flags prose drift when signatures/routes/keys/flags change — confirmed gap. The `**Source**` binding turns refactors into gate failures *after the fact* (doc goes red) but never *prompts* the author at commit time.

## 4. Risk-ranked gaps

- **Critical**: C1 pre-commit has zero doc awareness (code ships with untouched docs, hook stays green); C2 merges unblockable by design (no required checks; backstop = local hooks + `verify-push.sh` forensics); C3 README top-level numbers false (version/ADRs/risks/gates).
- **High**: H1 no doc-to-code manifest (11 packages + 3 surfaces untracked); H2 no snippet validation (DEVELOPMENT.md already ships a broken import); H3 TOOLS.md/ARCHITECTURE.md stale on the migration; H4 dead recovered-doc refs in governance files; H5 2 dead external links; H6 no docstring floor.
- **Medium**: M1 header-date rot; M2 orphan granularity + unindexed READMEs; M3 ROADMAP/DATABASE staleness; M4 CONFIG wording + 3 undocumented vars; M5 0/29 per-package READMEs; M6 mermaid-vs-code unverified.
- **Low**: L1 no badges (absent, not false); L2 no generated CLI reference (18 argparse CLIs); L3 no wiki (none referenced).

## 5. Tool recommendations (stack: Python/FastAPI, pre-commit framework, pip, local-only CI, zero CI budget)

Prefer extending the repo's own scripts over new dependencies (offline-friendly, no billing surface): Layer-1 as `scripts/docs/check-changed.py` (staged-diff × manifest, pure stdlib); markdown/style as repo-local rules in the same script (no network hook installs, no new daemons); `codespell` + `interrogate` via pip only if the repo wants them later — not required for v1. Manifest as `docs.manifest.yaml` seeded from existing `**Source**` bindings. Enforcement lands in `ci_gate.py` (`gate_docs_layer2`, offline) + the existing 15-day scheduled sweep for network checks, reusing its auto-issue path. GitHub Actions yaml stays as documentation-only (billing-disabled); branch-protection steps ship as copy-paste instructions for the day billing returns.
