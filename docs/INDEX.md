# JARVIS Complete Version-by-Version Documentation Index

Welcome to the central master index and LLM navigation map for the **JARVIS** repository, covering version-by-version documentation from initial commit (`v0.1.0`) to `HEAD` (`v3.0.0 Refactored`).

---

## 1. Version Tag Map

| Version Tag | Release Commit | Major Milestone / Feature Added |
| :--- | :--- | :--- |
| **`v0.1.0`** | `e13ee67` | Initial project structure & direct local Ollama client |
| **`v0.2.0`** | `ded44b9` | Interactive CLI chat loop with streaming stdout |
| **`v0.3.0`** | `8b1d0cb` | Initial in-tree architecture & development roadmap |
| **`v0.4.0`** | `e5c6fd6` | System prompt persona injection in message context |
| **`v0.5.0`** | `4034bf7` | Persistent Memory Core saving user preference facts |
| **`v0.7.0`** | `7803a93` | ContextBuilder assembling prompt, memory & chat turns |
| **`v0.8.0`** | `d43f6e9` | Structured Memory schema & multi-fact extraction |
| **`v1.0.0`** | `6316917` | Behavior-driven memory engine (`append`/`replace`/`delete`) |
| **`v2.0.0`** | `8519f65` | Complete architectural overhaul & prompt task classifier |
| **`v2.1.0`** | `df45be2` | Multi-backend support (`LlamaCppClient`) & YAML settings |
| **`v2.2.0`** | `b2c2211` | ChromaDB vector retriever & BM25 hybrid memory search |
| **`v2.3.0`** | `c84d53b` | `DocumentationAgent`, tool infrastructure & execution framework |
| **`v2.4.0`** | `6ea9796` | Platform expansion for commercial cloud LLM providers |
| **`v2.4.1`** | `1cab1b1` | Mermaid.js architecture visualizer in docs |
| **`v2.4.2`** | `6034224` | Custom Ollama `Modelfile` configuration |
| **`v2.5.0`** | `f9fa068` | FastAPI Web API Server & modern dark-mode Web UI |
| **`v3.0.0`** | `81e45f0` | Live catalog, security hardening & RAG knowledge subsystem |
| **`v3.0.0 Refactored`** | `ec0dc4e` | Single-tenant pragmatic hybrid architecture refactor |

---

## 2. Core Documentation Deliverables
- 📘 **[README.md](file:///home/sajan/JARVIS/README.md)**: Developer quickstart & package index.
- 📐 **[ARCHITECTURE.md](file:///home/sajan/JARVIS/ARCHITECTURE.md)**: Living architecture at `HEAD`, topology & Mermaid diagrams.
- 📜 **[HISTORY.md](file:///home/sajan/JARVIS/docs/HISTORY.md)**: Version-by-version milestone timeline (`v0.1.0` ➔ `v3.0.0 Refactored`).
- 🔌 **[API.md](file:///home/sajan/JARVIS/docs/API.md)**: Exported API signature history across all versions.
- 📝 **[CHANGELOG.md](file:///home/sajan/JARVIS/docs/CHANGELOG.md)**: Release notes for all version tags.
- 🛣️ **[ROADMAP.md](file:///home/sajan/JARVIS/docs/ROADMAP.md)**: Technical Debt Register (`DEBT-001` through `DEBT-007`) across commits.
- 🏥 **[HEALTH_REPORT.md](file:///home/sajan/JARVIS/docs/HEALTH_REPORT.md)**: Repository health metrics across versions.

---

## 3. Subsystem Modules (`docs/modules/`)
- [domain.md](file:///home/sajan/JARVIS/docs/modules/domain.md): Domain Entities (`v0.1.0` ➔ `v3.0.0 Refactored`)
- [brain.md](file:///home/sajan/JARVIS/docs/modules/brain.md): Cognitive Brain Engine (`v0.1.0` ➔ `v3.0.0 Refactored`)
- [models.md](file:///home/sajan/JARVIS/docs/modules/models.md): Multi-Provider LLM Pool (`v0.1.0` ➔ `v3.0.0 Refactored`)
- [memory.md](file:///home/sajan/JARVIS/docs/modules/memory.md): Persistent Memory (`v0.5.0` ➔ `v3.0.0 Refactored`)
- [guardrails.md](file:///home/sajan/JARVIS/docs/modules/guardrails.md): Safety Policy (`v0.1.0` ➔ `v3.0.0 Refactored`)
- [adapters.md](file:///home/sajan/JARVIS/docs/modules/adapters.md): I/O Protocol Adapters (`v0.1.0` ➔ `v3.0.0 Refactored`)
- [integrations.md](file:///home/sajan/JARVIS/docs/modules/integrations.md): OSS Integrations (`v0.1.0` ➔ `v3.0.0 Refactored`)

---

## 4. Architectural Decision Records (`docs/ADR/`)
- [ADR-001: Direct Ollama Integration & CLI](file:///home/sajan/JARVIS/docs/ADR/ADR-001-ollama-cli-integration.md) (`v0.1.0`)
- [ADR-002: JSON File Persistent Memory Core](file:///home/sajan/JARVIS/docs/ADR/ADR-002-json-file-persistent-memory.md) (`v0.5.0`)
- [ADR-003: Multi-Model Task Router & Overhaul](file:///home/sajan/JARVIS/docs/ADR/ADR-003-multi-model-task-router.md) (`v2.0.0`)
- [ADR-004: ChromaDB Semantic Memory & Hybrid BM25](file:///home/sajan/JARVIS/docs/ADR/ADR-004-chromadb-semantic-memory.md) (`v2.2.0`)
- [ADR-005: FastAPI Web Server & Single-Page App](file:///home/sajan/JARVIS/docs/ADR/ADR-005-fastapi-web-server-and-ui.md) (`v2.5.0`)
- [ADR-006: Pragmatic Hybrid Architecture](file:///home/sajan/JARVIS/docs/ADR/ADR-006-pragmatic-hybrid-architecture.md) (`v3.0.0 Refactored`)
- [ADR-007: Domain Purity & Standard Dataclasses](file:///home/sajan/JARVIS/docs/ADR/ADR-007-domain-purity-and-dataclasses.md) (`v3.0.0 Refactored`)
- [ADR-008: Tiered Tool Safety Policy & HITL Approval Gates](file:///home/sajan/JARVIS/docs/ADR/ADR-008-tiered-tool-safety-policy.md) (`v3.0.0 Refactored`)
- [ADR-009: Multi-Provider Failover & Circuit Breaker](file:///home/sajan/JARVIS/docs/ADR/ADR-009-multi-provider-circuit-breaker-failover.md) (`v3.0.0 Refactored`)
- [ADR-010: Adapters & Integrations Boundary Isolation](file:///home/sajan/JARVIS/docs/ADR/ADR-010-adapters-and-integrations-isolation.md) (`v3.0.0 Refactored`)
