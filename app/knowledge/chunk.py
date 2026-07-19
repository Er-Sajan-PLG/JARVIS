"""
Chunking for the JARVIS knowledge / RAG subsystem.

Turns extracted PDF pages (see ``app.knowledge.extract``) into fixed-size,
overlapping text chunks suitable for embedding + retrieval.

Design:
* A :class:`Chunk` carries the text plus the metadata needed to cite it later:
  ``doc_id``, ``filename``, ``title``, ``page`` (1-based), and a global
  ``chunk_index`` (stable within a document; used as the ChromaDB id).
* Chunking is **word-based** (split on whitespace, rejoin) so we never break a
  word across a boundary, and it needs no external tokenizer. Sizes are measured
  in characters against ``chunk_size`` / ``chunk_overlap``.
* Pages are processed in order; overlap is applied between consecutive chunks
  *within and across pages* so context isn't lost at page boundaries.
* Short trailing fragments are merged into the previous chunk. A short fragment
  that is the very first chunk (with nothing to merge into) is dropped only when
  other content follows; a sole short chunk is kept since it is the whole
  document and discarding it would lose all content.

This module is pure Python (no PDF/OCR/embedding deps) so it is easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    """One embeddable chunk of a document, with citation metadata."""

    doc_id: str
    filename: str
    title: str
    page: int            # 1-based page number the chunk came from
    chunk_index: int     # global 0-based index within the document
    text: str


def _split_into_chunks(
    text: str,
    chunk_size: int,
    overlap: int,
    start_index: int,
) -> tuple[list[str], int]:
    """
    Split ``text`` into overlapping word-based chunks.

    Returns (chunks, next_index) where ``next_index`` is the global chunk index
    to continue from for the following page/text segment.
    """
    words = text.split()
    if not words:
        return [], start_index

    chunks: list[str] = []
    idx = start_index
    i = 0
    step = max(1, chunk_size - overlap)  # advance by (size - overlap) words

    while i < len(words):
        piece = words[i : i + chunk_size]
        chunk_text = " ".join(piece).strip()
        if chunk_text:
            chunks.append(chunk_text)
            idx += 1
        i += step

    return chunks, idx


def chunk_document(
    title: str,
    filename: str,
    doc_id: str,
    pages: list,
    chunk_size: int = 1000,
    overlap: int = 150,
    min_chunk_chars: int = 50,
) -> list[Chunk]:
    """
    Build embeddable chunks from ordered, extracted pages.

    ``pages`` is a list of objects exposing ``.page_no`` and ``.text``
    (e.g. ``app.knowledge.extract.Page``). Pages are processed in order so the
    global ``chunk_index`` is stable and overlap flows across page boundaries.

    Returns a list of :class:`Chunk`.
    """
    chunks: list[Chunk] = []
    global_index = 0

    for page in pages:
        text = (getattr(page, "text", "") or "").strip()
        if not text:
            continue

        page_chunks, global_index = _split_into_chunks(
            text, chunk_size, overlap, global_index
        )

        for c in page_chunks:
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    filename=filename,
                    title=title,
                    page=getattr(page, "page_no", 0),
                    chunk_index=len(chunks),
                    text=c,
                )
            )

    # Merge or drop fragments shorter than min_chunk_chars.
    #
    # A fragment shorter than ``min_chunk_chars`` is merged into the previous
    # chunk so we don't embed tiny orphan snippets. The ONLY case we drop
    # rather than merge is when the short fragment is the very first chunk AND
    # has nothing before it to merge into (a genuine empty/garbage lead) — and
    # even then we keep it if it is the *sole* chunk, because that lone chunk
    # is the entire document and discarding it would lose all content.
    if min_chunk_chars > 0 and chunks:
        merged: list[Chunk] = []
        for ch in chunks:
            is_short = len(ch.text) < min_chunk_chars
            if is_short and merged:
                # Merge the short fragment into the previous chunk's text.
                prev = merged[-1]
                prev.text = (prev.text + " " + ch.text).strip()
            else:
                merged.append(ch)
        chunks = merged

    return chunks
