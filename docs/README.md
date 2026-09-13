# JARVIS Documentation Guide

Welcome to the **JARVIS Documentation Suite** — the architectural specifications,
release notes, diagnostic guides, decision records, and API contracts for JARVIS
across all versions (`v0.1.0` through `v3.0.1`).

**Start at [INDEX.md](INDEX.md)** — the master navigation map.

---

## 🗺️ Where to start

| Document | Purpose |
|---|---|
| **[INDEX.md](INDEX.md)** | Master navigation map — start here |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Living system topology and core invariants at `HEAD` |
| **[GOVERNANCE.md](GOVERNANCE.md)** | Decision authority, branching, quality gates, release process |
| **[DEVELOPMENT.md](DEVELOPMENT.md)** | Daily workflow, local setup, testing standards, git conventions |
| **[API_CONTRACT.md](API_CONTRACT.md)** | REST/WS endpoints, auth, data models, error codes |
| **[ROADMAP.md](ROADMAP.md)** | Sprint plan and technical debt register |
| **[ACCEPTED_RISKS.md](ACCEPTED_RISKS.md)** | Risk register — owners and review dates for every CRITICAL/HIGH finding |

---

## ⚙️ Automation & CI

| Document | Purpose |
|---|---|
| **[CI-GATE-SOTA.md](CI-GATE-SOTA.md)** | The local CI engine: 22 checks, 8 published contexts, threat model |
| **[CI-TOKEN-PERMISSIONS.md](CI-TOKEN-PERMISSIONS.md)** | Which GitHub token needs which permission, and why |
| **[N8N-SETUP.md](N8N-SETUP.md)** | Standing up the n8n automation plane |
| **[N8N-HANDOVER.md](N8N-HANDOVER.md)** | Editing workflows in the UI and reading changes back |
| **[GITHUB-APP-SETUP.md](GITHUB-APP-SETUP.md)** | Migrating CI auth from long-lived PATs to GitHub Apps |
| **[BRANCH_PROTECTION_SETUP.md](BRANCH_PROTECTION_SETUP.md)** | Branch protection status and the platform limits hit |

---

## 📋 History & Decisions

| Document | Purpose |
|---|---|
| **[CHANGELOG.md](CHANGELOG.md)** | User-facing release notes (`v0.1.0` ➔ `v3.0.1`) |
| **[DEVLOG.md](DEVLOG.md)** | Developer architectural evolution and decision rationale |
| **[HISTORY.md](HISTORY.md)** | Git database archaeology and milestone timeline |
| **[adr/](adr/)** | Architectural Decision Records — **ADR-001 through ADR-013** |
| **[DECISIONS-AUTONOMOUS-2026-09-10.md](DECISIONS-AUTONOMOUS-2026-09-10.md)** | Autonomous decisions: what, why, rejected alternatives |
| **[AUDIT-USAT.md](AUDIT-USAT.md)** | Forensic architecture audit (implemented vs documented) |
| **[HEALTH_REPORT.md](HEALTH_REPORT.md)** | ⚠️ **Historical snapshot (2026-07-28)** — not current |
| **[CAPABILITY_TRACKER.md](CAPABILITY_TRACKER.md)** | Capability Contract v1.0 compliance tracking (JARVIS ↔ PROFESSOR-J) |
| **[CAPABILITY-CONTRACT.md](CAPABILITY-CONTRACT.md)** | The contract itself |

---

## 📂 Subfolder structure

| Directory | Content |
|---|---|
| [`architecture/`](architecture/) | Mermaid flowcharts: components, cognitive brain, model routing, memory, data flow, startup |
| [`modules/`](modules/) | Per-subsystem guides: domain, brain, models, memory, guardrails, adapters, integrations |
| [`adr/`](adr/) | Architectural Decision Records (ADR-001 → ADR-013) |
| [`migrations/`](migrations/) | v2→v3 migration notes and tombstones |
| [`timelines/`](timelines/) | Evolution and symbol timelines |

Reference documents: **[API.md](API.md)** (class/method signatures),
**[CONFIG.md](CONFIG.md)**, **[DATABASE.md](DATABASE.md)**, **[MEMORY.md](MEMORY.md)**,
**[LLM.md](LLM.md)**, **[TOOLS.md](TOOLS.md)**, **[DEBUGGING.md](DEBUGGING.md)**,
**[CODING_STANDARDS.md](CODING_STANDARDS.md)**, **[SYMBOL_LINEAGE.md](SYMBOL_LINEAGE.md)**.

---

## 📌 Contributor guidelines

1. **Source of truth**: the repository state is authoritative. If a document and
   the code disagree, the code wins — and the document is a bug.
2. **Feature timelines**: distinguish **Feature Commit Author Date** (when the code
   was authored) from **Tag Release Date**.
3. **Version bumping**: `python3 scripts/bump_version.py patch|minor|major`.
4. **No absolute paths in links.** Use repo-relative markdown links; this repo has
   lived at more than one path.
