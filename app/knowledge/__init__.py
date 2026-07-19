"""
JARVIS knowledge / RAG subsystem.

Separate from personal memory (app/memory/). Handles ingestion of research
papers (PDF, including scanned/image-only pages via OCR), chunking, embedding
into ChromaDB, retrieval-augmented generation, and saving important findings
into long-term memory.

Public surface:
    from app.knowledge import ingest_pdf, PaperStore, answer, save_finding
"""

# Imports are done defensively (per-module) so the package stays importable
# while individual subsystems are built out incrementally.
from app.knowledge.extract import extract_pages, Page, build_ocr_engine, OCREngine
from app.knowledge.chunk import chunk_document, Chunk

# These are added as they are implemented in later steps.
try:
    from app.knowledge.store import PaperStore
except ModuleNotFoundError:  # pragma: no cover - not built yet
    pass

try:
    from app.knowledge.rag import answer
except ModuleNotFoundError:  # pragma: no cover - not built yet
    pass

try:
    from app.knowledge.findings import save_finding
except ModuleNotFoundError:  # pragma: no cover - not built yet
    pass

try:
    from app.knowledge.ingest import ingest_pdf
except ModuleNotFoundError:  # pragma: no cover - not built yet
    pass

__all__ = [
    "extract_pages",
    "Page",
    "build_ocr_engine",
    "OCREngine",
    "chunk_document",
    "Chunk",
    "PaperStore",
    "answer",
    "save_finding",
    "ingest_pdf",
]

