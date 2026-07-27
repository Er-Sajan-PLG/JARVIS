# JARVIS Documentation Master Index & LLM Navigation Map

Welcome to the central master index and LLM navigation map for **JARVIS**, covering full architectural history, component guides, decision records, and API signatures from initial commit (`v0.1.0`) to `HEAD` (`v3.0.1`).

---

## 1. Master Documentation Deliverables

| Category | File | Description |
| :--- | :--- | :--- |
| 📘 **Quickstart** | [README.md](file:///home/sajan/JARVIS/README.md) | Project Overview, Quickstart & Commands |
| 📐 **Living Architecture** | [ARCHITECTURE.md](file:///home/sajan/JARVIS/docs/ARCHITECTURE.md) | Living System Topology & Core Invariants at HEAD |
| 🔌 **API Signatures** | [API.md](file:///home/sajan/JARVIS/docs/API.md) | Public API Reference & Method Signatures History |
| 📝 **Release Notes** | [CHANGELOG.md](file:///home/sajan/JARVIS/docs/CHANGELOG.md) | Version Release Notes (`v0.1.0` ➔ `v3.0.1`) |
| 💻 **Developer Log** | [DEVLOG.md](file:///home/sajan/JARVIS/docs/DEVLOG.md) | Architectural Evolution & Feature Shift Log |
| 📜 **Git Archaeology** | [HISTORY.md](file:///home/sajan/JARVIS/docs/HISTORY.md) | Git Database Code Archaeology & Milestone Timeline |
| 🩺 **Diagnostic Matrix** | [DEBUGGING.md](file:///home/sajan/JARVIS/docs/DEBUGGING.md) | Verified Error Codes, Symptoms & Fixes Matrix |
| 🛣️ **Engineering Roadmap** | [ROADMAP.md](file:///home/sajan/JARVIS/docs/ROADMAP.md) | Technical Debt Register (`DEBT-001` - `DEBT-007`) |
| 🏥 **Repository Health** | [HEALTH_REPORT.md](file:///home/sajan/JARVIS/docs/HEALTH_REPORT.md) | Subsystem Code Quality Metrics across Releases |

---

## 2. High-Level Architecture Guides (`docs/architecture/`)

- 🧩 **[Component Topology](file:///home/sajan/JARVIS/docs/architecture/components.md)**: High-Level Mermaid Component Flowcharts
- 🧠 **[Cognitive Engine](file:///home/sajan/JARVIS/docs/architecture/cognitive_brain.md)**: Brain Request Cycle & Tiered Safety Gate Policy
- ⚡ **[Model Routing Pool](file:///home/sajan/JARVIS/docs/architecture/model_routing.md)**: Multi-Provider Pool & Circuit Breakers
- 🧠 **[Memory Subsystem](file:///home/sajan/JARVIS/docs/architecture/memory_subsystem.md)**: Hybrid BM25 & Chroma Vector Search Architecture
- 🌊 **[Streaming Data Flow](file:///home/sajan/JARVIS/docs/architecture/data_flow.md)**: End-to-End Async Streaming Data Flow
- 🚀 **[Composition Root Bootstrap](file:///home/sajan/JARVIS/docs/architecture/startup_flow.md)**: ApplicationContainer Bootstrap Sequence

---

## 3. Subsystem Architectural Modules (`docs/modules/`)

- 📦 **[domain.md](file:///home/sajan/JARVIS/docs/modules/domain.md)**: Pure Python 3.11+ Dataclass Models (`app/domain/`)
- 🧠 **[brain.md](file:///home/sajan/JARVIS/docs/modules/brain.md)**: Cognitive Brain Engine (`app/brain/`)
- 🤖 **[models.md](file:///home/sajan/JARVIS/docs/modules/models.md)**: LLM Provider Pool & Model Router (`app/models/`)
- 💾 **[memory.md](file:///home/sajan/JARVIS/docs/modules/memory.md)**: Persistent Memory Façade (`app/memory/`)
- 🛡️ **[guardrails.md](file:///home/sajan/JARVIS/docs/modules/guardrails.md)**: Tiered Tool Safety Policy & Decorator (`app/guardrails/`)
- 🔌 **[adapters.md](file:///home/sajan/JARVIS/docs/modules/adapters.md)**: REST & WebSocket Stream Adapters (`app/adapters/`)
- 🧩 **[integrations.md](file:///home/sajan/JARVIS/docs/modules/integrations.md)**: Isolated ChromaDB Vector Store & OCR Backends (`app/integrations/`)
- ⚙️ **[config.md](file:///home/sajan/JARVIS/docs/modules/config.md)**: Configuration Engine (`app/config/`)
- 🎨 **[frontend.md](file:///home/sajan/JARVIS/docs/modules/frontend.md)**: Web Single-Page Application (`frontend/`)
- 🛠️ **[scripts.md](file:///home/sajan/JARVIS/docs/modules/scripts.md)**: Automation & Version Bumper Scripts (`scripts/`)
- 🧪 **[tests.md](file:///home/sajan/JARVIS/docs/modules/tests.md)**: Unit & Stress Performance Test Suite (`tests/`)

---

## 4. Architectural Decision Records (`docs/adr/`)

- [ADR-001: Direct Ollama Integration & CLI](file:///home/sajan/JARVIS/docs/adr/ADR-001-ollama-cli-integration.md) (`v0.1.0`)
- [ADR-002: JSON File Persistent Memory Core](file:///home/sajan/JARVIS/docs/adr/ADR-002-json-file-persistent-memory.md) (`v0.5.0`)
- [ADR-003: Multi-Model Task Router & Overhaul](file:///home/sajan/JARVIS/docs/adr/ADR-003-multi-model-task-router.md) (`v2.0.0`)
- [ADR-004: ChromaDB Semantic Memory & Hybrid BM25](file:///home/sajan/JARVIS/docs/adr/ADR-004-chromadb-semantic-memory.md) (`v2.2.0`)
- [ADR-005: FastAPI Web Server & Single-Page App](file:///home/sajan/JARVIS/docs/adr/ADR-005-fastapi-web-server-and-ui.md) (`v2.5.0`)
- [ADR-006: Pragmatic Hybrid Architecture](file:///home/sajan/JARVIS/docs/adr/ADR-006-pragmatic-hybrid-architecture.md) (`v3.0.0 Refactored`)
- [ADR-007: Domain Purity & Dataclass Models](file:///home/sajan/JARVIS/docs/adr/ADR-007-domain-purity-and-dataclasses.md) (`v3.0.0 Refactored`)
- [ADR-008: Tiered Tool Safety Policy & Decorator](file:///home/sajan/JARVIS/docs/adr/ADR-008-tiered-tool-safety-policy.md) (`v3.0.0 Refactored`)
- [ADR-009: Multi-Provider Circuit Breaker Failover](file:///home/sajan/JARVIS/docs/adr/ADR-009-multi-provider-circuit-breaker-failover.md) (`v3.0.0 Refactored`)
- [ADR-010: Isolation of Third-Party Adapters & Integrations](file:///home/sajan/JARVIS/docs/adr/ADR-010-adapters-and-integrations-isolation.md) (`v3.0.0 Refactored`)

---

## 5. System Metadata Graphs (`docs/metadata/`)

- 📊 **`docs/metadata/api_graph.json`**: Extracted Public API Symbol Lineage
- 📊 **`docs/metadata/module_graph.json`**: Subsystem Module Topology & Imports
- 📊 **`docs/metadata/history_graph.json`**: Version Tag History & Commit Lineage
- 📊 **`docs/metadata/knowledge_graph.json`**: System Concept Map
