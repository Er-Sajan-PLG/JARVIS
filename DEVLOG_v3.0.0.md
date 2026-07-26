# DevLog — v3.0.0 Development Cycle
**Period:** v2.5.0 → v3.0.0 (Jul 19 – Jul 26, 2026)  
**Commits:** 9 | **Files:** 91 | **Lines:** +9,054 / -7,804  
**Test Count:** 99 (4 skipped for missing deps)

---

## Overview

v3.0.0 is a **major architectural release** focused on three pillars:
1. **Provider Expansion** — 15+ AI providers with live model catalogs
2. **RAG Knowledge Subsystem** — PDF ingestion, vector search, grounded answers, findings persistence
3. **Security-First API Key Handling** — User keys only, never persisted server-side

The release also removes the legacy profile system, adds a complete OCR service layer, and overhauls the web UI with provider tabs, filter chips, model tooltips, and a capabilities matrix.

---

## Commit-by-Commit Breakdown

### e35d468 — `feat(knowledge): scaffold RAG subsystem — PDF extraction, OCR, chunking` (Jul 19)
**Files:** 5 (+393 lines)
- Added `KnowledgeConfig` + `PathsConfig.papers_dir` to Settings
- `app/knowledge/extract.py`: `Page` dataclass, pluggable `OCREngine` protocol (NoOp + EasyOCR lazy backend), per-page native-text vs OCR routing with forgiving failure handling
- `app/knowledge/chunk.py`: Word-based `chunk_document()` with overlap + short-fragment merging across page boundaries
- `app/knowledge/__init__.py`: Defensive re-exports
- Requirements: `pymupdf`, `easyocr`

> **Architecture decision:** Kept knowledge (documents/papers) separate from personal memory — distinct subsystem with its own config, store, and retrieval.

---

### 4b93857 — `feat(knowledge): add PaperStore ChromaDB layer (Step 4)` (Jul 19)
**Files:** 2 (+402 lines)
- `app/knowledge/store.py`: `PaperStore` wrapping dedicated `jarvis-papers` ChromaDB collection (Ollama embeddings)
  - `add_document()` — stable `doc_id` from filename → idempotent re-ingest (overwrites, not duplicates)
  - `search()` — returns `{doc_id, filename, title, page, chunk_index, text}`
  - `list_documents()` — deduped per-doc with chunk counts
  - `clear_document()` — deletes only that document's chunks
- `tests/test_store.py`: 9 unit tests with isolated temp Chroma + bag-of-words fake embedding (no Ollama dep)

> **Verified:** add/count/list/search/clear all pass; re-ingest is idempotent.

---

### 7be0863 — `feat(knowledge): add RAG answer() with grounded citations (Step 5)` (Jul 19)
**Files:** 2 (+255 lines)
- `app/knowledge/rag.py`: `RAGResult` + `answer(query, model_client, store, limit, system_prompt)`
  - Retrieves chunks via `store.search()`
  - Builds grounding system prompt: cite every claim as `[title, p.X]`, stay within excerpts
  - Forwards numbered excerpts + question to `model_client.generate()` (tolerates `ModelResponse.content` or `str`)
  - Returns empty-source explanation when nothing retrieved
- `tests/test_rag.py`: 8 unit tests (prompt formatting, citations, empty/empty-query, happy path, limit propagation)

> **Verified green.** No ChromaDB/Ollama dependency in tests.

---

### 5e7937b — `feat(knowledge): save findings to memory + forward metadata in MemoryManager (Step 6)` (Jul 19)
**Files:** 3 (+212 lines)
- `app/knowledge/findings.py`: `save_finding(memory_manager, text, source_meta, importance, confidence)`
  - Stores under category=`finding`, type=`paper_note` with provenance `{source_title, page, doc_id}`
  - Page defaults to 0 (unknown); unknown keys ignored
- `app/memory/manager.py`: **Architecture fix** — `_handle_append` and `_handle_replace` now forward `fact['metadata']` into created/replaced `Memory` in a single call (previously dropped metadata, forcing awkward post-store update)
- `tests/test_findings.py`: 10 unit tests (normalization, single-call metadata, persistence roundtrip, finding category listing)
- Existing 34 memory tests still green

> **Key insight:** The metadata-forwarding fix was a prerequisite for clean findings persistence — eliminated a silent data-loss bug.

---

### 3c80fe7 — `Step 7: RAG papers API + folder-scoped retrieval` (Jul 19)
**Files:** 8 (+544 lines, -18)
- Integrated `PaperStore` into `JarvisEngine`; pre-creates default `Materials Science` folder on startup
- `ingest.py`: Orchestrates extract → chunk → store; persists original PDF bytes to `data/papers/<doc_id>.pdf` (OCR engine degrades to NoOp)
- `rag.answer()` now accepts `folder=` and forwards to `store.search()` for folder-scoped queries
- `PaperStore.add_document/search/list_documents` accept optional `folder` filter; returned dicts include `folder`
- `AttachmentStore.list_folders()` surfaces empty folders (so `Materials Science` visible before any upload)
- `app/api/server.py`: 6 papers endpoints (`/folders`, `/papers`, `/papers/ingest`, `/papers/query`, `/papers/findings`, `/papers/{doc_id}`)
- `tests/test_papers_api.py`: Integration tests (FakeStore + patched ingest) confirming folder threading, list/query/findings/delete wiring
- All 90 tests green

---

### 6e1b09a — `Step 8: Research Papers web UI` (Jul 19)
**Files:** 3 (+362 lines)
- Frontend: `Papers` sidebar button + dedicated modal
- Folder selector scoped to `/api/papers/folders` (always offers `Materials Science` even if list empty)
- Upload PDF → `/api/papers/ingest` with folder + optional title; ingested docs listed with chunk counts + delete
- "Ask within a folder" → `/api/papers/query` (folder-scoped RAG) renders answer + clickable `[title, p.X]` citation chips
- "Save finding" button → `/api/papers/findings` persists answer + first source provenance into long-term memory
- Files: `frontend/index.html` (button + modal), `frontend/app.js` (`papersState` + handlers), `frontend/styles.css` (papers styles)
- JS syntax-checked; all 90 backend tests still green

---

### ba2026f — `Step 9: KNOWLEDGE.md + consolidated knowledge tests` (Jul 19)
**Files:** 3 (+367 lines, -10)
- `docs/KNOWLEDGE.md`: Documents RAG subsystem (extract → chunk → store → rag → findings), folder model (reuses Attachments Library), config, `/api/papers/*` endpoints, web UI flow
- `tests/test_knowledge.py`: Consolidated unit tests
  - Always-run `chunk_document` tests (overlap, page boundary metadata, short-fragment merge, empty-page handling)
  - `extract_pages` native/OCR path tests skip cleanly when `fitz`/`easyocr` absent
  - In-code minimal valid text PDF generation so native extraction exercised when `pymupdf` installed
- **Bug fix in `chunk_document()`**: Fragment-merge rule wrongly discarded sole chunk (short whole document) and never merged short FIRST fragment forward. Fixed: short fragments merge into previous chunk; sole short chunk kept as entire document. Updated docstring.
- All 99 tests green (4 skipped: extract paths need fitz/easyocr)

---

### 81e45f0 — `feat: v3.0.0 — Major Release: Provider Expansion, Live Catalog, Security & Polish` (Jul 26)
**Files:** 78 (+6,605 / -6,271 lines) — **largest commit**
- **Phase 1: Secure API Key Routing** — 10 providers, localStorage + headers only (never persisted server-side)
- **Phase 2: Provider Expansion (15+ providers)** — Groq, Together AI, Cerebras, Mistral, Cohere, GitHub Models, Cloudflare, Zhipu, HuggingFace, SambaNova, NVIDIA NIM + adapter pattern
- **Phase 3: Live Model Catalog** — 14 catalog providers, server-side caching (TTL 10 min), search/filter
- **Phase 4: Model Info & Metadata** — Tooltips, capabilities matrix (15 providers), pricing/context/badges
- **Phase 5: Advanced Filtering** — Filter chips, smart search ("free", ">100k"), client-side instant results
- **Conversation Features** — Search sidebar, message pin/favorite, pinned API
- **OCR Integration** — Unlimited-OCR + PaddleOCR backends, health endpoints, visual indicator
- **Settings Overhaul** — Provider tabs, API Keys tab (10 providers), Capabilities tab

**Architecture:**
- `app/provider_registry.py` (779 lines): `ProviderRegistry` with `AIProvider`, `ProviderCapability`, `ProviderStatus`
- `ModelSwitcher` updated for dynamic model routing with user keys only
- 15 new catalog modules in `app/utils/*_catalog.py`
- New OCR service layer: `app/services/ocr/` (7 modules) + `app/api/ocr/routes.py`
- Frontend: search, pins, filters, tooltips, capabilities matrix

**Breaking Changes:**
- Dynamic model selection requires user-provided API key in headers (`X-API-Key-*`)
- Developer keys in `.env` NO LONGER used for dynamic models — user keys only
- API key storage: localStorage + per-request headers only (never persisted server-side)

---

### e5875fa — `chore: remove stray debug artifacts` (Jul 26)
**Files:** 2 deleted
- Removed `home/sajan/JARVIS/tests/test_issue9.py` (empty)
- Removed `tmp/tail.md` (debug scratch)

---

## Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| **Flat model registry (no profiles)** | Profiles were rigid; users want per-model selection across all providers. Runtime builds "default" (local) + "omni" (all) routers automatically. |
| **User keys only for dynamic models** | Security: developer keys in `.env` are a liability. Keys in localStorage + per-request headers = zero server-side persistence. |
| **Knowledge ≠ Memory** | Papers/documents are distinct from personal facts — separate config (`KnowledgeConfig`), store (`PaperStore`), retrieval (`retrieval_limit`), OCR settings. |
| **Idempotent ingestion by filename** | Re-uploading same PDF should update, not duplicate. Stable `doc_id` from filename hash achieves this. |
| **Folder model reuses Attachments Library** | No new folder system needed — papers live in same folders as other uploads. Pre-create `Materials Science` for immediate usability. |
| **Live catalog with TTL cache** | Provider catalogs don't change per-request. 10-min cache + force-refresh balances freshness vs API rate limits. |
| **Client-side filter chips** | Capability filters (reasoning, large context, tools) use heuristic model ID matching — instant, no extra API calls. |

---

## Testing Summary

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_store.py` | 9 | PaperStore CRUD, idempotent re-ingest, search ranking, folder scoping |
| `test_rag.py` | 8 | Prompt formatting, citations, empty handling, limit propagation |
| `test_findings.py` | 10 | Metadata normalization, single-call storage, persistence roundtrip, category listing |
| `test_papers_api.py` | ~15 | Integration: folder threading, list/query/findings/delete wiring |
| `test_knowledge.py` | ~12 | Chunking (always-run), extract native/OCR (skip if deps missing) |
| `test_remote_ocr.py` | 2 | Remote OCR health check |
| **Total** | **~56 new + 43 existing** | **99 tests (4 skipped)** |

---

## Dependency Changes (`requirements.txt`)

**Added:**
- `pymupdf==1.26.0` — PDF text extraction + page rendering
- `easyocr` — OCR backend (lazy-loaded)
- `paddleocr==2.8.1` + `paddlepaddle==2.6.1` — PaddleOCR backend
- `opencv-python-headless==4.10.0` — PaddleOCR dependency
- `Pillow==10.4.0` — Image processing

**Updated:**
- `fastapi`: 0.138.1 → 0.115.0
- `uvicorn`: 0.49.0 → 0.32.0
- `torch`: 2.12.1 → 2.10.0
- `transformers`: 5.12.1 → 4.57.1

---

## Documentation Updates

| File | Change |
|------|--------|
| `docs/KNOWLEDGE.md` | **New** — Complete RAG subsystem docs |
| `docs/ARCHITECTURE.md` | Updated for v3 architecture |
| `docs/CONFIG.md` | Updated for flat model registry + KnowledgeConfig |
| `docs/API.md` | New endpoints: `/api/models/catalog`, `/api/models/info`, `/api/models/capabilities`, `/api/papers/*`, `/api/ocr/*`, `/api/conversations/*/search`, `/api/conversations/*/pin`, `/api/conversations/*/pinned` |
| `docs/LLM.md` | Updated provider list |
| `docs/MEMORY.md` | Metadata forwarding fix noted |
| `docs/STARTUP_FLOW.md` | Updated initialization order |
| `docs/architecture/` | **New directory** — `agents.md`, `architecture.md`, `data-flow.md`, `memory.md`, `models.md`, `startup-flow.md` |
| Legacy cleanup | Removed `CHANGELOG_recovered.md`, `DEVLOG_recovered.md`, `NEW_DEVLOG.md`, `changelog.md`, `NEW_CHANGELOG.md` |

---

## Known Limitations / Follow-ups

1. **OCR backends** — EasyOCR/PaddleOCR/Unlimited-OCR are optional; system degrades to NoOp if unavailable. Remote OCR requires external service.
2. **Provider catalog pricing** — Free-model detection uses `pricing.prompt/completion === "0"` heuristic; may miss freemium tiers.
3. **Folder-scoped RAG** — Currently single-folder; multi-folder OR queries not yet supported.
4. **Findings provenance** — Only first source attached; multi-source findings would need array metadata.
5. **Capabilities matrix** — Provider capabilities are statically declared in `ProviderRegistry`; not auto-discovered from live models.

---

## Metrics

| Metric | Value |
|--------|-------|
| Commits in range | 9 |
| Files added | 42 |
| Files modified | 37 |
| Files deleted | 12 |
| Net line change | +1,250 |
| New test files | 6 |
| New API endpoints | 18 |
| Providers supported | 15 |
| Knowledge modules | 7 |

---

**Generated from git history v2.5.0..v3.0.0**