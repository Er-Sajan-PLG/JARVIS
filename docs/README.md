# JARVIS Documentation Guide

**Status**: ACTIVE
**Type**: index
**Last Updated**: 2026-09-13

**Source of truth**: the repository state. If a document and the code disagree,
the code wins — and the document is a bug.

> **Historical note (2026-09-13):** this directory previously shipped **two**
> competing navigation maps (`README.md` and `INDEX.md`) plus a set of
> auto-generated stubs and frozen snapshots presented without a banner. They
> drifted, contradicted each other, and described files that no longer exist.
> `INDEX.md` was deleted; `README.md` is the only map. See
> `docs/DOC-GOVERNANCE.md` for the convention that prevents a recurrence.

---

## 🗺️ Where to start

| Document | Purpose |
|---|---|
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Living system topology and core invariants at `HEAD` |
| **[GOVERNANCE.md](GOVERNANCE.md)** | Decision authority, branching, quality gates, release process |
| **[DEVELOPMENT.md](DEVELOPMENT.md)** | Daily workflow, local setup, testing standards, git conventions |
| **[API_CONTRACT.md](API_CONTRACT.md)** | REST/WS endpoints, auth, data models, error codes |
| **[ROADMAP.md](ROADMAP.md)** | Sprint plan and technical debt register |
| **[ACCEPTED_RISKS.md](ACCEPTED_RISKS.md)** | Risk register — owners and review dates for every CRITICAL/HIGH finding |
| **[VERSIONING.md](VERSIONING.md)** | How versions are derived from git tags and what cuts a release |
| **[DOC-GOVERNANCE.md](DOC-GOVERNANCE.md)** | How these documents are versioned, classified, and kept honest |

---

## ⚙️ Automation & CI

| Document | Purpose |
|---|---|
| **[CI-GATE-SOTA.md](CI-GATE-SOTA.md)** | The local CI engine: <!--fact:gate_count-->25<!--/fact--> checks, <!--fact:context_count-->9<!--/fact--> published contexts, threat model |
| **[CI-TOKEN-PERMISSIONS.md](CI-TOKEN-PERMISSIONS.md)** | Which GitHub token needs which permission, and why |
| **[GITHUB-APP-SETUP.md](GITHUB-APP-SETUP.md)** | Migrating CI auth from long-lived PATs to GitHub Apps |
| **[N8N-SETUP.md](N8N-SETUP.md)** | Standing up the n8n automation plane |
| **[N8N-HANDOVER.md](N8N-HANDOVER.md)** | Editing workflows in the UI and reading changes back |

---

## 🧩 Code references

| Document | Purpose |
|---|---|
| **[AGENTS.md](AGENTS.md)** | The `app/agents/` package (distinct from repo-root `AGENTS.md`) |
| **[TOOLS.md](TOOLS.md)** | The tool system under `app/tools/` |
| **[LLM.md](LLM.md)** | Model layer: clients, routing, providers |
| **[MEMORY.md](MEMORY.md)** | Memory subsystem architecture and lifecycle |
| **[DATABASE.md](DATABASE.md)** | Persistence: JSON stores and ChromaDB collections |
| **[CONFIG.md](CONFIG.md)** | Configuration system and defaults |
| **[DEBUGGING.md](DEBUGGING.md)** | Diagnostic matrix for `v0.1.0` → `v3.0.0` — **historical**, not current behaviour |
| **[SYMBOL_LINEAGE.md](SYMBOL_LINEAGE.md)** | Symbol birth/death/rename registry (generated) |

---

## 📋 Decisions & history

| Document | Purpose |
|---|---|
| **[adr/](adr/)** | Architectural Decision Records — **ADR-001 through ADR-013** |
| **[DECISIONS-AUTONOMOUS-2026-09-10.md](DECISIONS-AUTONOMOUS-2026-09-10.md)** | Autonomous decisions: what, why, rejected alternatives |
| **[CAPABILITY-CONTRACT.md](CAPABILITY-CONTRACT.md)** | The JARVIS ↔ PROFESSOR-J contract itself |
| **[CAPABILITY_TRACKER.md](CAPABILITY_TRACKER.md)** | Compliance tracking against that contract |
| **[SPRINT_1_2_COMPLETION.md](SPRINT_1_2_COMPLETION.md)** | Verified completion record for Sprints 1 and 2 |
| **[AUDIT-USAT.md](AUDIT-USAT.md)** | USAT audit report (dated snapshot — see its banner) |
| **[CHANGELOG.md](CHANGELOG.md)** | User-facing release notes |
| **[archive/](archive/)** | Frozen historical documents — **never cite as current** |

---

## 📂 Subfolder structure

| Directory | Content |
|---|---|
| [`architecture/`](architecture/) | Mermaid diagrams: components, cognitive brain, model routing, memory, data flow, startup |
| [`modules/`](modules/) | Per-subsystem guides: domain, brain, models, memory, guardrails, adapters, integrations |
| [`adr/`](adr/) | Architectural Decision Records (ADR-001 → ADR-013) |
| [`migrations/`](migrations/) | v2→v3 migration notes and symbol tombstones |
| [`timelines/`](timelines/) | Evolution and symbol timelines |
| [`archive/`](archive/) | Superseded snapshots and frozen release-cycle docs |

### A note on `modules/`

The `modules/` guides (`domain`, `brain`, `models`, `memory`, `guardrails`,
`adapters`, `integrations`) are **version-by-version histories** — they describe
how a subsystem evolved across releases. They are accurate as history.

Five sibling files were **deleted on 2026-09-13** because they were
auto-generated placeholder stubs with empty tables, or described files that do
not exist (`config.md`, `githooks.md`, `scripts.md`, `frontend.md`, `tests.md`).
Do not recreate them by hand; if a module guide is wanted, write it against the
code and follow `docs/DOC-GOVERNANCE.md`.

---

## 📌 Contributor guidelines

1. **Source of truth**: the repository state is authoritative. If a document and
   the code disagree, the code wins — and the document is a bug.
2. **Before writing any document, read `docs/DOC-GOVERNANCE.md` §10** — the
   mandatory doc-type contract. Declare a `**Type**`, scaffold with
   `scripts/new_doc.py`, and name the code you describe in `**Source**`. This is a
   blocking gate: `scripts/check_docs.py`, `githooks/pre-commit` and CI all enforce
   it.
3. **Feature timelines**: distinguish **Feature Commit Author Date** (when the code
   was authored) from **Tag Release Date**.
4. **Version bumping**: tags are cut automatically from conventional commits by
   `githooks/pre-push` → `scripts/version_bump.py --apply --tag-only`. Do not
   hand-edit a version string. See `docs/VERSIONING.md`.
5. **No absolute paths in links.** Use repo-relative markdown links; this repo has
   lived at more than one path.
6. **Every doc carries a status header and a type** — see `docs/DOC-GOVERNANCE.md`
   §2 and §10 for the allowed statuses and the type contract.
