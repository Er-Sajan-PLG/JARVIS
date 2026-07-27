# JARVIS Documentation Guide

Welcome to the **JARVIS Documentation Suite**. This directory contains the complete architectural specifications, release notes, diagnostic guides, decision records, and API contracts for JARVIS across all versions (`v0.1.0` through `v3.0.1`).

---

## 🗺️ Documentation Directory Map

- **[INDEX.md](file:///home/sajan/JARVIS/docs/INDEX.md)** — **Master Navigation Map & LLM Guide** (Start here!)
- **[ARCHITECTURE.md](file:///home/sajan/JARVIS/docs/ARCHITECTURE.md)** — Living System Topology & Core Architectural Invariants at `HEAD`.
- **[API.md](file:///home/sajan/JARVIS/docs/API.md)** — Public REST, WebSocket, and class API signatures across versions.
- **[CHANGELOG.md](file:///home/sajan/JARVIS/docs/CHANGELOG.md)** — User-facing release notes (`v0.1.0` ➔ `v3.0.1`).
- **[DEVLOG.md](file:///home/sajan/JARVIS/docs/DEVLOG.md)** — Developer architectural evolution & decision rationale log.
- **[HISTORY.md](file:///home/sajan/JARVIS/docs/HISTORY.md)** — Git Database Archaeology & Milestone Timeline.
- **[DEBUGGING.md](file:///home/sajan/JARVIS/docs/DEBUGGING.md)** — Master Diagnostic Matrix & Verified Error Fixes.
- **[ROADMAP.md](file:///home/sajan/JARVIS/docs/ROADMAP.md)**: Technical Debt Register (`DEBT-001` through `DEBT-007`).
- **[HEALTH_REPORT.md](file:///home/sajan/JARVIS/docs/HEALTH_REPORT.md)** — Repository Health Metrics across releases.

---

## 📂 Subfolder Structure

| Directory | Content Description |
| :--- | :--- |
| **[`docs/architecture/`](file:///home/sajan/JARVIS/docs/architecture/)** | High-level Mermaid flowcharts (`components.md`, `cognitive_brain.md`, `model_routing.md`, `memory_subsystem.md`, `data_flow.md`, `startup_flow.md`). |
| **[`docs/modules/`](file:///home/sajan/JARVIS/docs/modules/)** | Detailed subsystem module guides (`domain.md`, `brain.md`, `models.md`, `memory.md`, `guardrails.md`, `adapters.md`, `integrations.md`, `config.md`, `frontend.md`, `scripts.md`, `tests.md`). |
| **[`docs/adr/`](file:///home/sajan/JARVIS/docs/adr/)** | Architectural Decision Records (`ADR-001` through `ADR-010`). |
| **[`docs/metadata/`](file:///home/sajan/JARVIS/docs/metadata/)** | JSON symbol lineage & module topology graph data (`api_graph.json`, `module_graph.json`, `history_graph.json`, `knowledge_graph.json`). |

---

## 📌 Contributor Guidelines

1. **Source of Truth**: Git tags (`git tag`) are authoritative for release tag names and release publication dates.
2. **Feature Timelines**: All documentation entries must distinguish between **Feature Commit Author Date** (the date code was authored in Git) and **Tag Release Date**.
3. **Automated Bumping**: Use `python3 scripts/bump_version.py bump patch|minor|major` to update versions and generate release notes.