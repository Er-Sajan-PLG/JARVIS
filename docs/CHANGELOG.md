# JARVIS Release Changelog

All notable changes to the JARVIS project from initial commit (`1999e53`) to `HEAD` (`ec0dc4e`) are documented in this file.

## [v1.2.0.dirty] — setup + Sprint 3 base
- Setup: governance (8/8), CI gate (ratchet + worktree shadow), hooks, docs, USAT audit (76.2/100 production)
- Sprint 3: typed-state contract (`IntentState`); adapter reads wrapper; contract FAIL assertions present (3 targets)
- ARCH-003 (archive verified) + ARCH-007 (`HF_API_URL` externalised); SEC-002 masked
- Version: derived `v1.2.0.dirty` (from `pyproject.toml`); bump script implemented

---

## [v3.0.0 Refactored]
- **Timeline Metadata**: *Feature Author Date: 2026-07-28 (`ec0dc4e`)  |  Tag Release Date: 2026-07-28*
- **Feature Author Date**: 2026-07-28 (`c5a97b4` - `ec0dc4e`)
- **Tag Release Date**: 2026-07-28

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

## [v3.0.0]
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 (`81e45f0`)  |  Tag Release Date: 2026-07-26*
- **Feature Author Dates**: 2026-07-19 (RAG Subsystem `e35d468`-`ba2026f`) | 2026-07-26 (Catalog Expansion `81e45f0`)
- **Tag Release Date**: 2026-07-26 (`81e45f0`, `2c855c7`, `d23f5a0`)

### Added
- **Multi-Provider Live Catalog**: Dynamic discovery of cloud and local providers (Google AI Studio, Groq, Cerebras, SambaNova, NVIDIA NIM, OpenRouter, Ollama, llama.cpp).
- **RAG & Knowledge Subsystem**: PDF extraction, OCR service integration (PaddleOCR, UnlimitedOCR), chunking, vector embedding, and paper store retrieval API (`Steps 1-9`).
- **Web UI Enhancements**: Research Papers web UI tab, active provider switcher, live status indicator.

### Changed
- Security hardening across API endpoints and input parameter sanitization.

---

## [v2.5.0]
- **Timeline Metadata**: *Feature Author Date: 2026-07-18 (`f9fa068`)  |  Tag Release Date: 2026-07-18*
- **Feature Author Date**: 2026-07-18 (`f9fa068`)
- **Tag Release Date**: 2026-07-18

### Added
- **FastAPI Web API Server**: Interactive Web UI backend with REST endpoints for chat, sessions, and memory inspection.
- **Frontend Single-Page App**: Modern dark-mode web application in `frontend/`.

---

## [v2.4.2]
- **Timeline Metadata**: *Feature Author Date: 2026-07-14 (`6034224`)  |  Tag Release Date: 2026-07-14*
- **Feature Author Date**: 2026-07-14 (`6034224`)
- **Tag Release Date**: 2026-07-14

### Added
- Ollama `Modelfile` configuration for custom system instructions and default parameters.
- Configuration updates for local model runtime paths.

---

## [v2.4.1]
- **Timeline Metadata**: *Feature Author Date: 2026-07-13 (`1cab1b1`)  |  Tag Release Date: 2026-07-14*
- **Feature Author Date**: 2026-07-13 (`1cab1b1`)
- **Tag Release Date**: 2026-07-14

### Added
- Mermaid.js architecture diagrams in `docs/architecture/`.

---

## [v2.4.0]
- **Timeline Metadata**: *Feature Author Date: 2026-07-11 (`6ea9796`)  |  Tag Release Date: 2026-07-14*
- **Feature Author Date**: 2026-07-11 (`6ea9796`)
- **Tag Release Date**: 2026-07-14

### Added
- Expanded model backends (OpenAI, Anthropic, Cohere, Mistral, Together AI, Zhipu AI, HuggingFace Inference API).
- Centralized YAML configuration system in `config.yaml`.

---

## [v2.3.0]
- **Timeline Metadata**: *Feature Author Date: 2026-07-06 (`c84d53b`)  |  Tag Release Date: 2026-07-14*
- **Feature Author Date**: 2026-07-06 (`c84d53b`)
- **Tag Release Date**: 2026-07-14

### Added
- `DocumentationAgent`: Autonomous agent loop for analyzing git history and generating CHANGELOG/DEVLOG documentation.
- Tool Infrastructure: `ToolDefinition`, `ToolRegistry`, `ToolExecutor` (`read_file`, `write_file`, `append_file`, `git_log`, `git_diff_stat`, `git_diff_full`).

---

## [v2.2.0] - 2026-07-05 (`b2c2211`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`b2c2211`)  |  Tag Release Date: 2026-07-05*

### Added
- **Semantic Vector Memory**: ChromaDB integration (`VectorRetriever`) using `OllamaEmbeddingFunction` with `nomic-embed-text`.
- **Hybrid Retrieval**: `HybridRetriever` combining vector similarity and BM25 keyword search scores.

---

## [v2.1.0] - 2026-07-05 (`df45be2`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`df45be2`)  |  Tag Release Date: 2026-07-05*

### Added
- Multi-backend architecture (`LlamaCppClient`, `OllamaClient`).
- Token-by-token response streaming over stdout/HTTP.
- External YAML configuration loader (`get_settings()`).

---

## [v2.0.0] - 2026-07-03 (`8519f65`, `5fccb37`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-03 (`8519f65`)  |  Tag Release Date: 2026-07-03*

### Added
- Complete core architectural overhaul.
- Multi-model task router (`ModelRouter`) classifying prompts into `CODE`, `STEM`, `REASONING`, `DOCS`, `GENERAL`.
- Model switcher (`ModelSwitcher`) for runtime model swap.

---

## [v1.0.0] - 2026-06-29 (`6316917`, `db51ccc`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`6316917`)  |  Tag Release Date: 2026-06-29*

### Added
- Behavior-driven memory engine supporting `append`, `replace`, `ignore`, and `delete` actions.
- Multi-trigger fact extraction pipeline from user conversation turns.

---

## [v0.8.0] - 2026-06-29 (`d43f6e9`, `2922129`, `4f71baf`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`d43f6e9`)  |  Tag Release Date: 2026-06-29*

### Added
- Structured memory record schema (`Memory` dataclass with timestamps, importance scores, categories).
- Multi-fact extraction pipeline.

---

## [v0.7.0] - 2026-06-28 (`7803a93`, `9aa2fb2`, `b145614`, `7a840ee`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`7803a93`)  |  Tag Release Date: 2026-06-28*

### Added
- `ContextBuilder` for assembling system prompts, retrieved long-term memories, and conversation history.
- Separation of persistent memory facts from conversation message turns.

---

## [v0.5.0] - 2026-06-28 (`4034bf7`, `3cc9e4b`, `94e1956`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`4034bf7`)  |  Tag Release Date: 2026-06-28*

### Added
- Persistent Memory Core storing extracted user preferences to disk.
- Conversation history tracking in `OllamaClient`.

---

## [v0.4.0] - 2026-06-27 (`e5c6fd6`, `7491e9a`, `39b3d5b`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e5c6fd6`)  |  Tag Release Date: 2026-06-27*

### Added
- `SYSTEM_PROMPT` persona configuration injection.

---

## [v0.3.0] - 2026-06-27 (`8b1d0cb`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`8b1d0cb`)  |  Tag Release Date: 2026-06-27*

### Added
- Initial project architecture and technical roadmap documents in `docs/`.

---

## [v0.2.0] - 2026-06-27 (`ded44b9`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`ded44b9`)  |  Tag Release Date: 2026-06-27*

### Added
- Interactive CLI chat loop connecting user stdin/stdout to local LLM.

---

## [v0.1.0] - 2026-06-27 (`e13ee67`, `1999e53`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e13ee67`)  |  Tag Release Date: 2026-06-27*

### Added
- Initial project repository structure (`1999e53`).
- Initial Ollama API connection client (`e13ee67`).

# v0.1.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e13ee67`)  |  Tag Release Date: 2026-06-27*
## Release Summary
### Commit Window (3 commits)
#### Commit `1999e53` - Initial project structure
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 02:44:04 +0545
#### Commit `e13ee67` - Build Jarvis v0.1: Connect to Ollama
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 03:25:01 +0545
#### Commit `e13ee67` - Build Jarvis v0.1: Connect to Ollama
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 03:25:01 +0545

# v0.2.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`ded44b9`)  |  Tag Release Date: 2026-06-27*
## Release Summary
### Commit Window (2 commits)
#### Commit `ded44b9` - v0.2: working CLI chat loop with Ollama integration
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 04:59:01 +0545
#### Commit `ded44b9` - v0.2: working CLI chat loop with Ollama integration
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 04:59:01 +0545

# v0.3.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`8b1d0cb`)  |  Tag Release Date: 2026-06-27*
## Release Summary
### Commit Window (4 commits)
#### Commit `163f8a1` - Add .gitignore for Python project
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 12:58:53 +0545
#### Commit `163f8a1` - Add .gitignore for Python project
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 12:58:53 +0545
#### Commit `8b1d0cb` - Added Architecture and Roadmap in docs for what to do seamless development
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 13:05:30 +0545
#### Commit `8b1d0cb` - Added Architecture and Roadmap in docs for what to do seamless development
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 13:05:30 +0545

# v0.4.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e5c6fd6`)  |  Tag Release Date: 2026-06-27*
## Release Summary
### Commit Window (6 commits)
#### Commit `39b3d5b` - Making prompt
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 13:51:06 +0545
#### Commit `39b3d5b` - Making prompt
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 13:51:06 +0545
#### Commit `7491e9a` - prompt failure, prompts to prompt
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 14:03:01 +0545
#### Commit `7491e9a` - prompt failure, prompts to prompt
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 14:03:01 +0545
#### Commit `e5c6fd6` - added SYSTEM_PROMPT in messege
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 14:10:19 +0545
#### Commit `e5c6fd6` - added SYSTEM_PROMPT in messege
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 14:10:19 +0545

# v0.5.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`4034bf7`)  |  Tag Release Date: 2026-06-28*
## Release Summary
### Commit Window (6 commits)
#### Commit `94e1956` - Implement conversation history in OllamaClient
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 02:04:26 +0545
#### Commit `94e1956` - Implement conversation history in OllamaClient
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 02:04:26 +0545
#### Commit `3cc9e4b` - change model from deepseek r1:32b to qwen3:8b for faster development
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 02:11:32 +0545
#### Commit `3cc9e4b` - change model from deepseek r1:32b to qwen3:8b for faster development
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 02:11:32 +0545
#### Commit `4034bf7` - Persistent Memory Core
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 04:52:42 +0545
#### Commit `4034bf7` - Persistent Memory Core
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 04:52:42 +0545

# v0.7.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`7803a93`)  |  Tag Release Date: 2026-06-28*
## Release Summary
### Commit Window (8 commits)
#### Commit `7a840ee` - Save Fact based on preferences
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 05:16:44 +0545
#### Commit `7a840ee` - Save Fact based on preferences
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 05:16:44 +0545
#### Commit `b145614` - Fact Extraction
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 05:22:19 +0545
#### Commit `b145614` - Fact Extraction
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 05:22:19 +0545
#### Commit `9aa2fb2` -  JARVIS MEMORY SEPERATION FROM CONVERSATION ANDFACTS
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 16:23:10 +0545
#### Commit `9aa2fb2` -  JARVIS MEMORY SEPERATION FROM CONVERSATION ANDFACTS
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 16:23:10 +0545
#### Commit `7803a93` - Context Builder & Long-Term Memory Integration
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 22:50:49 +0545
#### Commit `7803a93` - Context Builder & Long-Term Memory Integration
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 22:50:49 +0545

# v0.8.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`d43f6e9`)  |  Tag Release Date: 2026-06-29*
## Release Summary
### Commit Window (2 commits)
#### Commit `d43f6e9` - [200~feat(v0.8): implement structured memory pipeline~
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 03:50:36 +0545
#### Commit `d43f6e9` - [200~feat(v0.8): implement structured memory pipeline~
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 03:50:36 +0545

# v1.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`6316917`)  |  Tag Release Date: 2026-06-29*
## Release Summary
### Commit Window (6 commits)
#### Commit `2922129` - feat(memory): implement multi-fact extraction pipeline
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 07:02:35 +0545
#### Commit `2922129` - feat(memory): implement multi-fact extraction pipeline
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 07:02:35 +0545
#### Commit `4f71baf` - feat(memory): implement behavior-driven memory engine and multi-fact extraction
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 08:56:24 +0545
#### Commit `4f71baf` - feat(memory): implement behavior-driven memory engine and multi-fact extraction
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 08:56:24 +0545
#### Commit `6316917` - feat(memory): implement multi-trigger extraction and behavior-based memory actions
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 12:13:20 +0545
#### Commit `6316917` - feat(memory): implement multi-trigger extraction and behavior-based memory actions
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 12:13:20 +0545

# v2.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-03 (`8519f65`)  |  Tag Release Date: 2026-07-03*
## Release Summary
### Commit Window (6 commits)
#### Commit `db51ccc` - feat(memory): implement multi-trigger extraction and behavior-based memory actions,left over
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 12:14:52 +0545
#### Commit `db51ccc` - feat(memory): implement multi-trigger extraction and behavior-based memory actions,left over
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 12:14:52 +0545
#### Commit `63addf6` - before big change in memory management
- **Author**: Er Sajan PLG | **Date**: 2026-07-02 09:31:29 +0545
#### Commit `63addf6` - before big change in memory management
- **Author**: Er Sajan PLG | **Date**: 2026-07-02 09:31:29 +0545
#### Commit `8519f65` - feat(core)!: JARVIS v2.0.0 - Complete architectural overhaul
- **Author**: Er Sajan PLG | **Date**: 2026-07-03 23:31:02 +0545
#### Commit `8519f65` - feat(core)!: JARVIS v2.0.0 - Complete architectural overhaul
- **Author**: Er Sajan PLG | **Date**: 2026-07-03 23:31:02 +0545

# v2.1.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`df45be2`)  |  Tag Release Date: 2026-07-05*
## Release Summary
### Commit Window (4 commits)
#### Commit `5fccb37` - Bug fixes and added archiecture, dev log and changelog for v2.0.0
- **Author**: Er Sajan PLG | **Date**: 2026-07-04 18:40:14 +0545
#### Commit `5fccb37` - Bug fixes and added archiecture, dev log and changelog for v2.0.0
- **Author**: Er Sajan PLG | **Date**: 2026-07-04 18:40:14 +0545
#### Commit `df45be2` - Multi-Backend + Streaming + External Config
- **Author**: Er Sajan PLG | **Date**: 2026-07-05 07:23:59 +0545
#### Commit `df45be2` - Multi-Backend + Streaming + External Config
- **Author**: Er Sajan PLG | **Date**: 2026-07-05 07:23:59 +0545

# v2.2.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`b2c2211`)  |  Tag Release Date: 2026-07-05*
## Release Summary
### Commit Window (2 commits)
#### Commit `b2c2211` - Semantic Memory with chromaDB installed vector_retriver, hybrid_retriever with keyword retriever, conversation_store, past_exchange and ollama isnallation for ebmedding, Agent imtegration for git automation with auto make devlog and change reverted
- **Author**: Er Sajan PLG | **Date**: 2026-07-05 22:01:06 +0545
#### Commit `b2c2211` - Semantic Memory with chromaDB installed vector_retriver, hybrid_retriever with keyword retriever, conversation_store, past_exchange and ollama isnallation for ebmedding, Agent imtegration for git automation with auto make devlog and change reverted
- **Author**: Er Sajan PLG | **Date**: 2026-07-05 22:01:06 +0545

# v2.3.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-06 (`c84d53b`)  |  Tag Release Date: 2026-07-14*
## Release Summary
### Commit Window (2 commits)
#### Commit `c84d53b` - feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:47:08 +0545
#### Commit `c84d53b` - feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:47:08 +0545

# v2.4.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-11 (`6ea9796`)  |  Tag Release Date: 2026-07-14*
## Release Summary
### Commit Window (2 commits)
#### Commit `6ea9796` - feat(platform): expand model backends and configuration system
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:47:54 +0545
#### Commit `6ea9796` - feat(platform): expand model backends and configuration system
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:47:54 +0545

# v2.4.1
- **Timeline Metadata**: *Feature Author Date: 2026-07-13 (`1cab1b1`)  |  Tag Release Date: 2026-07-14*
## Release Summary
### Commit Window (2 commits)
#### Commit `1cab1b1` - mermaid added in docs/architecture and mermaid dependencies
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:48:42 +0545
#### Commit `1cab1b1` - mermaid added in docs/architecture and mermaid dependencies
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:48:42 +0545

# v2.4.2
- **Timeline Metadata**: *Feature Author Date: 2026-07-14 (`6034224`)  |  Tag Release Date: 2026-07-14*
## Release Summary
### Commit Window (2 commits)
#### Commit `6034224` - chore: update configuration and add Ollama Modelfile
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:48:42 +0545
#### Commit `6034224` - chore: update configuration and add Ollama Modelfile
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:48:42 +0545

# v2.5.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-18 (`f9fa068`)  |  Tag Release Date: 2026-07-18*
## Release Summary
### Commit Window (2 commits)
#### Commit `f9fa068` - feat: add web UI, FastAPI server, and fix batch of issues
- **Author**: Er Sajan PLG | **Date**: 2026-07-18 18:10:01 +0545
#### Commit `f9fa068` - feat: add web UI, FastAPI server, and fix batch of issues
- **Author**: Er Sajan PLG | **Date**: 2026-07-18 18:10:01 +0545

# v3.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 (`81e45f0`)  |  Tag Release Date: 2026-07-26*
## Release Summary
### Commit Window (18 commits)
#### Commit `e5875fa` - chore: remove stray debug artifacts (home/ duplicate, tmp/ scratch)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 10:16:49 +0545
#### Commit `e5875fa` - chore: remove stray debug artifacts (home/ duplicate, tmp/ scratch)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 10:16:49 +0545
#### Commit `e35d468` - feat(knowledge): scaffold RAG subsystem — PDF extraction, OCR, chunking
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 13:53:07 +0545
#### Commit `e35d468` - feat(knowledge): scaffold RAG subsystem — PDF extraction, OCR, chunking
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 13:53:07 +0545
#### Commit `4b93857` - feat(knowledge): add PaperStore ChromaDB layer (Step 4)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 13:59:54 +0545
#### Commit `4b93857` - feat(knowledge): add PaperStore ChromaDB layer (Step 4)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 13:59:54 +0545
#### Commit `7be0863` - feat(knowledge): add RAG answer() with grounded citations (Step 5)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 14:19:27 +0545
#### Commit `7be0863` - feat(knowledge): add RAG answer() with grounded citations (Step 5)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 14:19:27 +0545
#### Commit `5e7937b` - feat(knowledge): save findings to memory + forward metadata in MemoryManager (Step 6)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 14:31:40 +0545
#### Commit `5e7937b` - feat(knowledge): save findings to memory + forward metadata in MemoryManager (Step 6)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 14:31:40 +0545
#### Commit `3c80fe7` - Step 7: RAG papers API + folder-scoped retrieval
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 15:36:23 +0545
#### Commit `3c80fe7` - Step 7: RAG papers API + folder-scoped retrieval
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 15:36:23 +0545
#### Commit `6e1b09a` - Step 8: Research Papers web UI
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 15:40:44 +0545
#### Commit `6e1b09a` - Step 8: Research Papers web UI
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 15:40:44 +0545
#### Commit `ba2026f` - Step 9: KNOWLEDGE.md + consolidated knowledge tests
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 15:49:02 +0545
#### Commit `ba2026f` - Step 9: KNOWLEDGE.md + consolidated knowledge tests
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 15:49:02 +0545
#### Commit `81e45f0` - feat: v3.0.0 — Major Release: Provider Expansion, Live Catalog, Security & Polish
- **Author**: Er Sajan PLG | **Date**: 2026-07-26 01:40:15 +0545
#### Commit `81e45f0` - feat: v3.0.0 — Major Release: Provider Expansion, Live Catalog, Security & Polish
- **Author**: Er Sajan PLG | **Date**: 2026-07-26 01:40:15 +0545
