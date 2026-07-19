"""
High-level ingestion pipeline for research papers.

Orchestrates the lower-level pieces (extract → chunk → store) into one call the
API can use:

    1. Build the configured OCR engine (lazy; NoOp if OCR is disabled or the
       backend can't be imported).
    2. extract_pages()  — native text + per-page OCR of scanned pages
    3. chunk_document() — word-based overlapping chunks
    4. store.add_document() — embed into ChromaDB (PaperStore)
    5. Persist the original PDF bytes under data/papers/<doc_id>.pdf so the
       document can be re-ingested or audited later without re-uploading.

The module is import-safe: heavy deps (pymupdf, easyocr) stay lazy inside the
steps that need them, so importing ``ingest_pdf_bytes`` never pulls them in.
"""

from __future__ import annotations

import os
from typing import Optional

from app.config.settings import get_settings, Settings
from app.knowledge.extract import extract_pages, build_ocr_engine
from app.knowledge.chunk import chunk_document


def ingest_pdf_bytes(
    pdf_bytes: bytes,
    filename: str,
    store,
    title: Optional[str] = None,
    folder: str = "",
    settings: Optional[Settings] = None,
    persist_dir: Optional[str] = None,
) -> dict:
    """Ingest a single PDF into the knowledge base.

    Args:
        pdf_bytes: raw PDF file contents.
        filename:  original file name (used for the title default + doc_id).
        store:     a :class:`PaperStore` (ChromaDB-backed).
        title:     optional human title; defaults to the filename stem.
        folder:    optional folder label to scope retrieval (e.g. the name of
                   an Attachments Library folder like "Materials Science").
        settings:  optional Settings; defaults to the global singleton.
        persist_dir: optional override for where PDF bytes are saved
                     (defaults to Settings.paths.papers_dir).

    Returns:
        {"doc_id", "title", "filename", "folder", "chunk_count", "pages",
         "ocr_pages"}
        ``pages`` is the number of pages that yielded text; ``ocr_pages`` is how
        many of those required OCR.
    """
    if not pdf_bytes:
        raise ValueError("empty PDF bytes")

    settings = settings or get_settings()
    kcfg = settings.knowledge
    title = (title or "").strip() or os.path.splitext(os.path.basename(filename))[0]

    # 1. OCR engine (NoOp if disabled or backend unavailable).
    try:
        ocr_engine = build_ocr_engine(
            kcfg.ocr_engine, langs=kcfg.ocr_languages, gpu=False
        )
    except Exception:  # pragma: no cover - env dependent
        ocr_engine = build_ocr_engine("none")

    # 2. Extract text per page (native + OCR as needed).
    pages = extract_pages(
        pdf_bytes,
        ocr_engine=ocr_engine,
        ocr_text_threshold=kcfg.ocr_text_threshold,
    )

    # 3. Chunk.
    doc_id = store._make_doc_id(filename)
    chunks = chunk_document(
        title=title,
        filename=filename,
        doc_id=doc_id,
        pages=pages,
        chunk_size=kcfg.chunk_size,
        overlap=kcfg.chunk_overlap,
        min_chunk_chars=kcfg.min_chunk_chars,
    )

    # 4. Store (embedding + metadata).
    used_doc_id = store.add_document(
        filename=filename, title=title, chunks=chunks, doc_id=doc_id, folder=folder
    )

    # 5. Persist the original PDF bytes for re-ingestion / auditing.
    _persist_pdf(pdf_bytes, used_doc_id, persist_dir, settings)

    ocr_pages = sum(1 for p in pages if p.source == "ocr")
    return {
        "doc_id":      used_doc_id,
        "title":       title,
        "filename":    filename,
        "folder":      folder or "",
        "chunk_count": len(chunks),
        "pages":       len(pages),
        "ocr_pages":   ocr_pages,
    }


def _persist_pdf(
    pdf_bytes: bytes, doc_id: str, persist_dir: Optional[str], settings: Settings
) -> None:
    """Save the original PDF bytes to data/papers/<doc_id>.pdf (best-effort)."""
    base = persist_dir or str(settings.paths.papers_dir)
    try:
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, f"{doc_id}.pdf"), "wb") as f:
            f.write(pdf_bytes)
    except OSError as exc:  # non-fatal: ingestion still succeeded
        from app.utils.logging_setup import get_logger
        get_logger(__name__).warning("Could not persist PDF bytes: %s", exc)
