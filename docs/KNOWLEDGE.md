# Knowledge / Research Assistant (RAG Subsystem)

JARVIS's research-assistant feature lets you ingest PDF research papers into a
vector knowledge base and ask questions across them — with answers grounded in
retrieved excerpts and cited as `[title, p.X]`. It is built for a Materials
Science Master's workload: scanned/read PDFs, organized into folders (e.g.
**Materials Science**), and surfaced through the web UI.

This subsystem is **separate** from personal memory (`app/memory/`) and from the
Attachments Library (`app/attachments/`). Papers are embedded into their own
ChromaDB collection (`jarvis-papers`) and retrieved only by the RAG path, but
they reuse the Attachment Library's **folder** model so the UI stays consistent.

---

## Architecture

```
            ┌─────────────────────────────┐
 upload ──▶ │  /api/papers/ingest         │
 (PDF)      │  ingest_pdf_bytes(...)      │
            │   1. build_ocr_engine()     │
            │   2. extract_pages()        │  native text + per-page OCR
            │   3. chunk_document()        │  word-based overlapping chunks
            │   4. PaperStore.add_document │  embed → ChromaDB (jarvis-papers)
            │   5. persist PDF bytes       │  data/papers/<doc_id>.pdf
            └──────────────┬──────────────┘
                           │
   ask ─▶ /api/papers/query │ rag.answer(query, model_client, store, folder=)
            │                  └─ store.search(query, limit, folder=)
            │                        └─ ChromaDB query (where={"folder": folder})
            │
            ▼
   RAGResult(answer, sources)  →  frontend renders answer + [title, p.X] chips
            │
   Save finding ─▶ /api/papers/findings  →  MemoryManager.store (category="finding")
```

### Modules (`app/knowledge/`)

| File | Responsibility |
|------|----------------|
| `extract.py` | Per-page text extraction. Native text via `pymupdf` (`fitz`); pages with `< ocr_text_threshold` chars are rendered to PNG and OCR'd via `easyocr`. Returns ordered `Page` objects (`source` = `"text"` / `"ocr"`). Heavy imports are lazy. |
| `chunk.py` | Pure-Python, word-based overlapping chunker. Produces `Chunk` records carrying `doc_id`, `filename`, `title`, `page` (1-based), `chunk_index`, `text`. Overlap flows across page boundaries. |
| `store.py` | `PaperStore` — ChromaDB-backed store (collection `jarvis-papers`, `OllamaEmbeddingFunction(nomic-embed-text)`, cosine space). `add_document` / `search(folder=)` / `list_documents(folder=)` / `clear_document`. `doc_id` is a stable hash of the filename (idempotent re-ingest). |
| `rag.py` | `answer()` — retrieves chunks (optionally folder-scoped), builds a grounding prompt requiring `[title, p.X]` citations, calls `model_client.generate`, returns `RAGResult(answer, sources)`. Folder filter is forwarded to `store.search` so queries can be "asked within a folder". |
| `findings.py` | `save_finding()` — persists a research note into long-term memory (`MemoryManager`, `category="finding"`, `memory_type="paper_note"`). Normalizes `source_meta` (always includes `page`, defaults `0`). |
| `ingest.py` | `ingest_pdf_bytes()` — orchestrates extract → chunk → store and persists the original PDF bytes. OCR engine degrades to `NoOp` on import/backend failure so digital PDFs never fail to ingest. |

---

## Folder model

Papers are scoped to folders that live in the **Attachments Library** folder
system (`AttachmentStore`). A paper's `folder` is stored on every chunk's
metadata, so retrieval can be limited to a single folder.

* On startup `JarvisEngine` **pre-creates** the `Materials Science` folder
  (`attachments.create_folder("Materials Science")`) so the UI always has a
  sensible default upload target.
* `AttachmentStore.list_folders()` returns **all** known folder paths, including
  empty ones (unlike `list_tree()`, which only shows folders that contain files).
* `GET /api/papers/folders` exposes these to the frontend.

---

## Configuration (`KnowledgeConfig`, `PathsConfig`)

Set via `config.yaml` / environment (see `docs/CONFIG.md`). Defaults:

```yaml
knowledge:
  chunk_size: 1000          # characters per chunk
  chunk_overlap: 150        # overlap between chunks (context continuity)
  min_chunk_chars: 50       # fragments shorter than this are merged/dropped
  retrieval_limit: 6        # default chunks returned by a query
  ocr_engine: "easyocr"     # "easyocr" | "none"  (none = digital PDFs only)
  ocr_languages: ["en"]
  ocr_text_threshold: 30    # native-text char count below which a page is OCR'd

paths:
  chroma_dir: data/chroma
  ollama_url: http://localhost:11434
  embed_model: nomic-embed-text
  papers_dir: data/papers    # persisted original PDF bytes (<doc_id>.pdf)
```

> **Prerequisites for live ingestion:** `pymupdf` (for text + page rendering)
> and an Ollama server at `ollama_url` serving `embed_model` (`nomic-embed-text`)
> for embeddings. `easyocr` is only needed for scanned/image-only pages.

---

## API Reference (`/api/papers/*`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/api/papers/folders` | List all folder names (incl. empty). |
| `GET`  | `/api/papers?folder=<name>` | List ingested documents (filterable by folder). Returns `{documents, count}`. |
| `POST` | `/api/papers/ingest` (multipart: `file`, `folder="Materials Science"`, `title`) | Upload + ingest a PDF; also saves the bytes to the Attachment Library. Returns `{doc_id, title, filename, folder, chunk_count, pages, ocr_pages}`. |
| `POST` | `/api/papers/query` (`{query, folder?, limit?}`) | Folder-scoped RAG answer. Returns `{answer, sources}` where each source has `doc_id, filename, title, page, chunk_index, folder, text`. |
| `POST` | `/api/papers/findings` (`{text, source_meta?}`) | Save a research finding into long-term memory. Returns the stored memory metadata. |
| `DELETE` | `/api/papers/{doc_id}` | Remove a document's chunks and its persisted PDF. Returns `{ok, removed_chunks}`. |

---

## Web UI

Open the app (`python -m app.api.server` → `http://localhost:8000`) and click
**📚 Papers** in the sidebar:

1. **Pick a folder** from the dropdown (defaults to *All folders*; the
   pre-created **Materials Science** folder is always offered).
2. **Upload a PDF** into the selected folder. It is ingested and appears in the
   document list with its chunk count.
3. **Ask within the folder** — type a question; the answer is shown with
   clickable `[title, p.X]` citation chips for each retrieved excerpt.
4. **Save finding** — persists the answer (with the first source as provenance)
   into long-term memory, available later under **🧠 Memories**.

---

## Testing

The knowledge layer is covered by focused unit/integration tests that isolate
heavy dependencies (ChromaDB, Ollama, `fitz`, `easyocr`):

* `tests/test_store.py` — `PaperStore` with a deterministic bag-of-words fake
  embedding function and an isolated temp ChromaDB dir.
* `tests/test_rag.py` — `answer()` prompt construction, empty-source handling,
  and the folder-scoped happy path via a stub model client.
* `tests/test_findings.py` — `save_finding()` metadata normalization and memory
  category/type.
* `tests/test_papers_api.py` — FastAPI `TestClient` integration tests that swap
  the real `PaperStore` for an in-memory `FakeStore` and patch
  `app.api.server.ingest_pdf_bytes`, validating route wiring, the default
  folder, folder threading, list/query/findings/delete, and the
  `finding` category.

OCR-dependent paths are skipped automatically when `easyocr` is unavailable.
