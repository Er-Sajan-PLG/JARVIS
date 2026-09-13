# Changelog

**Status**: HISTORICAL
**Last Updated**: 2026-07-26
## [v3.0.0] - 2026-07-26

### Added
- **Provider Registry & Adapter Pattern** (`app/provider_registry.py`): New central `ProviderRegistry` class managing 15+ AI providers (OpenRouter, Google, Groq, GitHub Models, NVIDIA NIM, Mistral, Cohere, HuggingFace, Cloudflare, Zhipu, Ollama, Together AI, Cerebras, SambaNova, LlamaCPP). Each provider has capabilities metadata (OpenAI-compatible, reasoning, code generation, STEM, documentation, realtime, free models, context window, max output tokens) and model categories.
- **Live Model Catalog** (`app/utils/provider_catalog.py`, 15 new catalog modules): Unified live model browsing across all providers with 10-minute server-side TTL caching, search/filter, and automatic free-model detection. New catalog modules: `anthropic_catalog.py`, `cerebras_catalog.py`, `cloudflare_ai_catalog.py`, `cohere_catalog.py`, `github_models_catalog.py`, `groq_catalog.py`, `hf_catalog.py`, `mistral_catalog.py`, `nvidia_nim_catalog.py`, `openai_catalog.py`, `openrouter_catalog.py`, `together_catalog.py`, `zhipu_catalog.py`, `sambanova_models` (in provider_catalog), `google_models` (in provider_catalog).
- **Dynamic Model Selection with User-Provided API Keys**: Dynamic model routing now requires user-provided API keys sent via `X-API-Key-*` headers (localStorage + per-request headers only). Developer keys in `.env` are NO LONGER used for dynamic models — user keys only. API keys are never persisted server-side.
- **RAG Knowledge Subsystem** (`app/knowledge/` — 7 new modules, 5 test files):
  - **PDF Extraction & OCR** (`extract.py`): `Page` dataclass, pluggable `OCREngine` protocol (NoOp + EasyOCR lazy backend, Unlimited-OCR, PaddleOCR), per-page native-text vs OCR routing with forgiving per-page failure handling.
  - **Chunking** (`chunk.py`): Word-based `chunk_document()` with overlap and short-fragment merging across page boundaries; fixed bug where sole short chunks were discarded.
  - **ChromaDB PaperStore** (`store.py`): Persistent vector store (`jarvis-papers` collection, Ollama embeddings), idempotent ingestion (stable `doc_id` from filename), folder-scoped search, document listing with chunk counts, per-document deletion.
  - **RAG Answer Generation** (`rag.py`): `RAGResult` dataclass + `answer(query, model_client, store, limit, system_prompt)` with grounded citations `[title, p.X]`, empty-source handling.
  - **Findings Persistence** (`findings.py`): `save_finding(memory_manager, text, source_meta, importance, confidence)` stores findings under category=`finding`, type=`paper_note` with provenance metadata `{source_title, page, doc_id}`.
  - **Ingestion Pipeline** (`ingest.py`): Orchestrates extract → chunk → store, persists original PDF bytes to `data/papers/<doc_id>.pdf`.
  - **MemoryManager Metadata Forwarding** (`app/memory/manager.py`): `_handle_append` and `_handle_replace` now forward `fact['metadata']` into the created/replaced `Memory` in a single call (architecture fix).
- **Research Papers Web UI** (`frontend/app.js`, `frontend/index.html`, `frontend/styles.css`): Papers sidebar button + modal, folder selector (always offers pre-created "Materials Science"), PDF upload → `/api/papers/ingest`, document listing with chunk counts + delete, folder-scoped RAG query → `/api/papers/query` with clickable citation chips `[title, p.X]`, "Save finding" → `/api/papers/findings` into long-term memory.
- **OCR Service Layer** (`app/services/ocr/` — 7 new modules, `app/api/ocr/routes.py`): Multi-backend OCR service (Unlimited-OCR + PaddleOCR backends), health endpoints (`/api/ocr/health`, `/api/ocr/remote_health`, `/api/ocr/local_health`), visual OCR indicator in UI, thread-pool inference, PDF→image rendering via PyMuPDF.
- **Conversation Search & Pinning** (`app/api/server.py`, `app/conversation/manager.py`, `frontend/app.js`):
  - `/api/conversations/{conv_id}/search` — search messages within a conversation
  - `/api/conversations/{conv_id}/pin` — toggle pin status on a message
  - `/api/conversations/{conv_id}/pinned` — list pinned messages
  - Frontend: search sidebar, pin/unpin buttons on messages, pinned message styling
- **Capabilities Matrix Endpoint** (`/api/models/capabilities`): Provider capability comparison table (15 providers × 12 capabilities: OpenAI-compatible, reasoning, code generation, STEM, docs, realtime, free models, context window, max output, status, API key presence).
- **Model Info Tooltips** (Frontend): Hover tooltip on dynamic model options showing provider, model ID, context window, max output, input/output cost, badges (Free, Reasoning, Tools).
- **Advanced Model Filtering** (Frontend): Filter chips (Free only, Reasoning, Large Context ≥32k, Tools), smart search queries ("free", ">100k"), client-side instant results.
- **Omni Router Profile** (`app/models/switcher.py`): New "omni" router automatically built from all successfully loaded clients grouped by role; default profile prefers local Ollama when present.
- **KnowledgeConfig & PathsConfig.papers_dir** (`app/config/settings.py`): New `KnowledgeConfig` dataclass (chunk_size=1000, chunk_overlap=150, min_chunk_chars=50, retrieval_limit=6, ocr_engine="unlimited", ocr_languages=["en"], remote_ocr_url="", ocr_text_threshold=30), `PathsConfig.papers_dir` property.
- **External OCR Example** (`external/remote_ocr_example/`): Reference implementation for remote OCR service.
- **Consolidated Knowledge Tests** (`tests/test_knowledge.py`): Always-run `chunk_document` unit tests + `extract_pages` native/OCR path tests (skip cleanly when `fitz`/`easyocr` absent), in-code minimal valid text PDF generation.

### Changed
- **BREAKING: Dynamic Model Selection — User Keys Only**: Developer keys in `.env` are NO LONGER used for dynamic models. Users must provide API keys via Settings → API Keys tab (stored in localStorage) or `X-API-Key-*` headers per request. Keys are never persisted server-side.
- **BREAKING: Configuration — Profiles Removed**: `config.yaml` no longer uses `profiles` or `active_profile`. Model registry is flat; runtime builds "default" (local Ollama) and "omni" (all providers) routers automatically. `active_profile` defaults to `"default"`. Legacy `profiles` key in config is ignored with warning.
- **Model Selection UI Overhaul** (`frontend/app.js`): Provider tabs (Ollama, Omni, llama.cpp, Google, Grok, OpenRouter, Together, Cerebras, OpenAI, Anthropic, Configured, Unknown), dynamic catalog search per provider, filter chips, model info tooltips, free-model badge, context/pricing display.
- **Settings Overhaul** (`frontend/app.js`, `frontend/index.html`): Provider tabs, API Keys tab (10 providers: Google, Grok, OpenRouter, OpenAI, Anthropic, Together, Cerebras, Groq, SambaNova, NVIDIA), Capabilities tab (matrix table), keys stored in localStorage only.
- **OpenRouter Catalog**: Live free-model detection for default dynamic model selection.
- **Dynamic Providers List Expanded**: Added Groq, SambaNova, NVIDIA NIM, Together AI, Cerebras, OpenAI, Anthropic to dynamic catalog providers (previously only OpenRouter, Google, Grok).
- **ModelSwitcher Refactor** (`app/models/switcher.py`): Removed hardcoded profiles; builds clients from flat `settings.models`; constructs "omni" router from all clients grouped by role; default router prefers local Ollama.
- **PaperStore Folder Scoping** (`app/knowledge/store.py`, `app/knowledge/rag.py`): `add_document`, `search`, `list_documents` accept optional `folder` filter; returned dicts include `folder`.
- **AttachmentStore.list_folders()** (`app/attachments/store.py`): Now surfaces empty folders (so pre-created "Materials Science" folder is visible before any upload).
- **ConversationManager** (`app/conversation/manager.py`): Added `search_messages(query)`, `toggle_pin(index)`, `get_pinned_messages()`.
- **OCR Engine Configuration**: Default changed from `easyocr` to `unlimited` (Unlimited-OCR backend); `remote` engine option added for external OCR service.
- **Frontend Styles** (`frontend/styles.css`): +230 lines for papers modal, provider tabs, filter chips, model tooltips, capabilities matrix table, OCR health indicator, pinned message styling.
- **Requirements** (`requirements.txt`): Added `pymupdf`, `easyocr`, `paddleocr`, `unlimited-ocr` dependencies; updated `uvicorn` to 0.32.0.
- **Documentation Overhaul**: New `docs/KNOWLEDGE.md` (RAG subsystem docs), updated `docs/ARCHITECTURE.md`, `docs/CONFIG.md`, `docs/API.md`, `docs/LLM.md`, `docs/MEMORY.md`, `docs/STARTUP_FLOW.md`, new architecture docs under `docs/architecture/`, cleaned up legacy devlogs/changelogs.

### Fixed
- **Chunking Bug** (`app/knowledge/chunk.py`): Fragment-merge rule incorrectly discarded sole chunk (short whole document) and never merged short first fragment forward. Fixed: short fragments now merge into previous chunk; sole short chunk kept as entire document.
- **MemoryManager Metadata Drop** (`app/memory/manager.py`): `store()` previously dropped `fact['metadata']`, forcing awkward post-store update. Fixed: `_handle_append` and `_handle_replace` now forward metadata in single call.
- **Knowledge `__init__` Import Naming** (`app/knowledge/__init__.py`): Fixed `ingest_pdf` → `ingest_pdf_bytes` export.
- **Remote OCR Health Check**: Pre-flight check before PDF ingestion when `ocr_engine: "remote"` configured.
- **Ollama Model Detection**: Live model listing for dynamic catalog.

### Refactored
- **Provider Catalog Consolidation** (`app/utils/provider_catalog.py`): Unified search interface across 14 providers with dynamic imports, client-side capability filtering (reasoning, large context, tools), free-model detection from pricing.
- **Model Factory** (`app/models/factory.py`): Updated for new provider catalog integration.
- **Settings Load** (`app/config/settings.py`): Removed profile logic, added `KnowledgeConfig`, ignore legacy `profiles` key.
- **Documentation Cleanup**: Removed `docs/CHANGELOG_recovered.md`, `docs/DEVLOG_recovered.md`, `docs/NEW_DEVLOG.md`, `docs/changelog.md`, `NEW_CHANGELOG.md`, `home/sajan/JARVIS/tests/test_issue9.py`, `tmp/tail.md`.

### Performance
- **Live Catalog Caching**: 10-minute TTL server-side cache (`_global_cache`, `_catalog_lock`) for all provider catalogs.
- **Client-Side Filtering**: Instant filter-chip results without additional API calls.
- **Thread-Pool OCR Inference**: `ThreadPoolExecutor` with configurable workers for non-blocking OCR processing.

### Security
- **API Key Handling**: User keys stored only in browser localStorage; transmitted via `X-API-Key-*` headers per request; never written to `.env` or server disk; developer keys in `.env` ignored for dynamic models.
- **OCR Remote Service Health**: Pre-ingestion health check prevents silent failures.

### Documentation
- **KNOWLEDGE.md**: Complete RAG subsystem documentation (extract → chunk → store → rag → findings), folder model, config, API endpoints, web UI flow.
- **Architecture Docs**: New `docs/architecture/` directory with `agents.md`, `architecture.md`, `data-flow.md`, `memory.md`, `models.md`, `startup-flow.md`.
- **API.md**: Updated with new endpoints (`/api/models/catalog`, `/api/models/info`, `/api/models/capabilities`, `/api/papers/*`, `/api/ocr/*`, `/api/conversations/*/search`, `/api/conversations/*/pin`, `/api/conversations/*/pinned`).

### Tests
- **New Test Files** (99 total tests, 4 skipped for missing deps):
  - `tests/test_store.py` (9 tests): PaperStore add/count/list/search/clear, idempotent re-ingest.
  - `tests/test_rag.py` (8 tests): Prompt formatting, citation markers, empty/empty-query handling, happy path, limit propagation.
  - `tests/test_findings.py` (10 tests): Normalization, single-call metadata storage, persistence roundtrip, finding category listing.
  - `tests/test_papers_api.py` (integration): Folder threading, list/query/findings/delete wiring.
  - `tests/test_knowledge.py` (consolidated): Chunk_document (overlap, page boundary metadata, short-fragment merge, empty-page), extract_pages native/OCR paths (skip when deps absent), in-code PDF generation.
  - `tests/test_remote_ocr.py`: Remote OCR health check.

### Removed
- **Configuration Profiles System**: `active_profile`, `profiles` mapping removed from `Settings` and `config.yaml`.
- **Legacy DevLogs/Changelogs**: `docs/CHANGELOG_recovered.md`, `docs/DEVLOG_recovered.md`, `docs/NEW_DEVLOG.md`, `docs/changelog.md`, `NEW_CHANGELOG.md`.
- **Debug Artifacts**: `home/sajan/JARVIS/tests/test_issue9.py`, `tmp/tail.md`.
- **Duplicate Model Configs**: Per-role model entries collapsed to single entry per provider in `config.yaml` (e.g., one `openrouter` instead of `openrouter_general`, `openrouter_code`, etc.).

### Breaking Changes
1. **Dynamic Model Selection Requires User API Keys**: Developer keys in `.env` are NO LONGER used for dynamic models. Users must provide keys via Settings → API Keys tab (localStorage) or `X-API-Key-*` headers. Keys never persisted server-side.
2. **Profiles Removed from Configuration**: `config.yaml` no longer uses `profiles` or `active_profile`. Flat model registry only. Runtime builds "default" (local) and "omni" (all providers) routers. Legacy `profiles` key ignored with warning.
3. **API Key Persistence Endpoint Changed**: `POST /api/settings` no longer writes keys to `.env` or `os.environ`. Keys managed client-side only.
4. **Model Config Structure**: `config.yaml` models collapsed from per-role to single entry per provider.
5. **KnowledgeConfig Added**: New required config section for RAG/OCR settings.
6. **Default OCR Engine**: Changed from `easyocr` to `unlimited` (Unlimited-OCR backend).
7. **Frontend State Changes**: `state.modelProvider`, `state.modelSearch`, `state.filters`, `state.modelGroups`, `state.devMode` replace old model selection state.

---
Generated from git history v2.5.0..v3.0.0 (9 commits, 91 files changed, +9054/-7804 lines)
