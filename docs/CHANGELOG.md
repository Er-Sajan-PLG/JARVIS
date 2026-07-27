# JARVIS Release Changelog

All notable changes to the JARVIS project from initial commit (`1999e53`) to `HEAD` (`ec0dc4e`) are documented in this file.

---

## [v3.0.0 Refactored] - 2026-07-28

### Added
- **Domain Layer (`app/domain/`)**: Pure Python 3.11+ dataclasses (`ContentSource`, `MemoryRecord`, `ExecutionPlan`, `SessionState`, `SafetyTier`).
- **Composition Root (`app/bootstrap.py`)**: `ApplicationContainer` dependency injection container wiring system singletons.
- **Cognitive Brain Engine (`app/brain/`)**: `IntentAnalyzer`, `TaskPlanner`, `ExecutionRunner`, `ResponseSynthesizer`.
- **Tiered Tool Safety Policy (`app/guardrails/`)**: `ToolSafetyPolicy` and `@safety_gate` decorators enforcing `SAFE`, `SENSITIVE`, and `DESTRUCTIVE` approval gates.
- **Resource Manager & Circuit Breaker (`app/resources/`)**: `ResourceManager`, `TokenBudgetManager`, `RateLimitTracker`, `ProviderHealthMonitor`.
- **I/O Protocol Adapters (`app/adapters/`)**: REST HTTP routes, WebSocket / SSE streaming adapters, Bearer token authentication (`JARVIS_API_KEY`).
- **Third-Party Integrations (`app/integrations/`)**: OCR service backends and `ChromaVectorStore` wrapper isolating ChromaDB vector search.
- **Telemetry Observability (`app/telemetry/`)**: `EventLogger`, `Tracer`, `MetricsCollector`.

### Changed
- Refactored `ModelRouter` in `app/models/router.py` to support dynamic provider registration and automatic 429/503 circuit breaker failover.
- Refactored `MemoryService` in `app/memory/service.py` to act as a domain-pure memory façade.
- Reorganized test suite into `tests/unit/` and `tests/performance/`.

### Fixed
- Fixed memory file corruption handling in `MemoryStore` to automatically quarantine bad JSON files to `.corrupt-*.bak`.
- Fixed token budgeting in `ContextBuilder` to prevent context window overflow.

---

## [v3.0.0] - 2026-07-26 (`81e45f0`, `2c855c7`, `d23f5a0`)

### Added
- **Multi-Provider Live Catalog**: Dynamic discovery of cloud and local providers (Google AI Studio, Groq, Cerebras, SambaNova, NVIDIA NIM, OpenRouter, Ollama, llama.cpp).
- **RAG & Knowledge Subsystem**: PDF extraction, OCR service integration (PaddleOCR, UnlimitedOCR), chunking, vector embedding, and paper store retrieval API (`Steps 1-9`).
- **Web UI Enhancements**: Research Papers web UI tab, active provider switcher, live status indicator.

### Changed
- Security hardening across API endpoints and input parameter sanitization.

---

## [v2.5.0] - 2026-07-18 (`f9fa068`)

### Added
- **FastAPI Web API Server**: Interactive Web UI backend with REST endpoints for chat, sessions, and memory inspection.
- **Frontend Single-Page App**: Modern dark-mode web application in `frontend/`.

---

## [v2.4.2] - 2026-07-14 (`6034224`)

### Added
- Ollama `Modelfile` configuration for custom system instructions and default parameters.
- Configuration updates for local model runtime paths.

---

## [v2.4.1] - 2026-07-13 (`1cab1b1`)

### Added
- Mermaid.js architecture diagrams in `docs/architecture/`.

---

## [v2.4.0] - 2026-07-11 (`6ea9796`)

### Added
- Expanded model backends (OpenAI, Anthropic, Cohere, Mistral, Together AI, Zhipu AI, HuggingFace Inference API).
- Centralized YAML configuration system in `config.yaml`.

---

## [v2.3.0] - 2026-07-06 (`c84d53b`)

### Added
- `DocumentationAgent`: Autonomous agent loop for analyzing git history and generating CHANGELOG/DEVLOG documentation.
- Tool Infrastructure: `ToolDefinition`, `ToolRegistry`, `ToolExecutor` (`read_file`, `write_file`, `append_file`, `git_log`, `git_diff_stat`, `git_diff_full`).

---

## [v2.2.0] - 2026-07-05 (`b2c2211`)

### Added
- **Semantic Vector Memory**: ChromaDB integration (`VectorRetriever`) using `OllamaEmbeddingFunction` with `nomic-embed-text`.
- **Hybrid Retrieval**: `HybridRetriever` combining vector similarity and BM25 keyword search scores.

---

## [v2.1.0] - 2026-07-05 (`df45be2`)

### Added
- Multi-backend architecture (`LlamaCppClient`, `OllamaClient`).
- Token-by-token response streaming over stdout/HTTP.
- External YAML configuration loader (`get_settings()`).

---

## [v2.0.0] - 2026-07-03 (`8519f65`, `5fccb37`)

### Added
- Complete core architectural overhaul.
- Multi-model task router (`ModelRouter`) classifying prompts into `CODE`, `STEM`, `REASONING`, `DOCS`, `GENERAL`.
- Model switcher (`ModelSwitcher`) for runtime model swap.

---

## [v1.0.0] - 2026-06-29 (`6316917`, `db51ccc`)

### Added
- Behavior-driven memory engine supporting `append`, `replace`, `ignore`, and `delete` actions.
- Multi-trigger fact extraction pipeline from user conversation turns.

---

## [v0.8.0] - 2026-06-29 (`d43f6e9`, `2922129`, `4f71baf`)

### Added
- Structured memory record schema (`Memory` dataclass with timestamps, importance scores, categories).
- Multi-fact extraction pipeline.

---

## [v0.7.0] - 2026-06-28 (`7803a93`, `9aa2fb2`, `b145614`, `7a840ee`)

### Added
- `ContextBuilder` for assembling system prompts, retrieved long-term memories, and conversation history.
- Separation of persistent memory facts from conversation message turns.

---

## [v0.5.0] - 2026-06-28 (`4034bf7`, `3cc9e4b`, `94e1956`)

### Added
- Persistent Memory Core storing extracted user preferences to disk.
- Conversation history tracking in `OllamaClient`.

---

## [v0.4.0] - 2026-06-27 (`e5c6fd6`, `7491e9a`, `39b3d5b`)

### Added
- `SYSTEM_PROMPT` persona configuration injection.

---

## [v0.3.0] - 2026-06-27 (`8b1d0cb`)

### Added
- Initial project architecture and technical roadmap documents in `docs/`.

---

## [v0.2.0] - 2026-06-27 (`ded44b9`)

### Added
- Interactive CLI chat loop connecting user stdin/stdout to local LLM.

---

## [v0.1.0] - 2026-06-27 (`e13ee67`, `1999e53`)

### Added
- Initial project repository structure (`1999e53`).
- Initial Ollama API connection client (`e13ee67`).

# v0.1.0
## Release Summary
### Commit Window (3 commits)
#### Commit `1999e53` - Initial project structure
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 02:44:04 +0545
#### Commit `e13ee67` - Build Jarvis v0.1: Connect to Ollama
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 03:25:01 +0545
#### Commit `e13ee67` - Build Jarvis v0.1: Connect to Ollama
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 03:25:01 +0545

# v0.2.0
## Release Summary
### Commit Window (2 commits)
#### Commit `ded44b9` - v0.2: working CLI chat loop with Ollama integration
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 04:59:01 +0545
#### Commit `ded44b9` - v0.2: working CLI chat loop with Ollama integration
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 04:59:01 +0545
