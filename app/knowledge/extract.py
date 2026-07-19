"""
PDF text extraction for the JARVIS knowledge / RAG subsystem.

Two extraction paths, chosen per page:

1. Native text (fast): ``pymupdf`` (``fitz``) pulls the embedded text layer.
   Works for normal "digital" PDFs (text converted to PDF, LaTeX output, etc.).

2. OCR (scanned pages): if a page yields little/no native text — i.e. it is a
   scanned image or a picture of text — we render the page to a bitmap and run
   an OCR engine over it. This is what makes the subsystem handle
   image-only / scanned research papers, not just word-processed PDFs.

The decision is made **per page** so a PDF that is 90% digital but has a couple
of scanned figures/appendices only pays the OCR cost on those pages.

Concerns are kept separate:
* ``extract_pages`` is the high-level orchestrator (page loop + routing).
* ``OCREngine`` is a Protocol; ``EasyOCREngine`` / ``NoOpOCREngine`` are the
  pluggable implementations. Swapping OCR backends does not touch the rest.

Heavy imports (``fitz``, ``easyocr``) are lazy (inside functions/classes) so
this module is safe to import even before those optional deps are installed.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Protocol, Optional

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class Page:
    """One extracted PDF page."""

    page_no: int          # 1-based page number
    text: str             # extracted text (native or OCR'd)
    source: str = "text"  # "text" = native layer, "ocr" = scanned/OCR'd


class OCREngine(Protocol):
    """Pluggable OCR backend. Implementations live behind this interface."""

    def ocr_image(self, image_bytes: bytes) -> str:
        """Run OCR on a single PNG/JPEG image and return the recognized text."""
        ...


class NoOpOCREngine:
    """OCR disabled. Returns empty text — used when ``ocr_engine == "none"``."""

    def ocr_image(self, image_bytes: bytes) -> str:
        return ""


class EasyOCREngine:
    """
    OCR via ``easyocr`` (https://github.com/JaidedAI/EasyOCR).

    The ``easyocr`` module and its model download are heavy, so the reader is
    imported and the model is instantiated **lazily** on first use. Construction
    arguments (``langs``, ``gpu``) are cached so repeated pages reuse one reader.
    """

    def __init__(self, langs: Optional[list[str]] = None, gpu: bool = False):
        self._langs = langs or ["en"]
        self._gpu = gpu
        self._reader = None  # created on first ocr_image() call

    def _get_reader(self):
        if self._reader is None:
            try:
                import easyocr  # lazy import — only when OCR is actually needed
            except ImportError as exc:  # pragma: no cover - env dependent
                raise RuntimeError(
                    "easyocr is not installed. Run `pip install easyocr` or set "
                    "knowledge.ocr_engine to 'none' to skip OCR of scanned pages."
                ) from exc
            logger.info("Loading EasyOCR reader (langs=%s, gpu=%s)…", self._langs, self._gpu)
            self._reader = easyocr.Reader(self._langs, gpu=self._gpu)
        return self._reader

    def ocr_image(self, image_bytes: bytes) -> str:
        reader = self._get_reader()
        # easyocr.readtext accepts a raw bytes object / numpy array / path.
        results = reader.readtext(image_bytes, detail=0, paragraph=True)
        if isinstance(results, str):
            return results
        return "\n".join(str(line) for line in results)


def build_ocr_engine(engine_name: str, langs: Optional[list[str]] = None, gpu: bool = False) -> OCREngine:
    """
    Factory for the configured OCR backend.

    ``engine_name`` is taken from ``KnowledgeConfig.ocr_engine``
    ("easyocr" | "none"). Unknown names fall back to the no-op engine so a bad
    config can never crash ingestion of digital PDFs.
    """
    name = (engine_name or "none").lower()
    if name == "easyocr":
        return EasyOCREngine(langs=langs, gpu=gpu)
    # "none" or anything unrecognized -> skip OCR entirely.
    if name != "none":
        logger.warning("Unknown ocr_engine '%s'; OCR disabled.", engine_name)
    return NoOpOCREngine()


def _render_page_to_png(page, dpi: int = 200) -> bytes:
    """Render a fitz page to PNG bytes at the given DPI for OCR."""
    try:
        import fitz  # lazy import; guaranteed present when called from extract_pages
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("pymupdf is required for PDF extraction.") from exc
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=mat)
    buf = io.BytesIO()
    pix.save(buf, "png")
    return buf.getvalue()


def extract_pages(
    pdf_bytes: bytes,
    ocr_engine: Optional[OCREngine] = None,
    ocr_text_threshold: int = 30,
    dpi: int = 200,
) -> list[Page]:
    """
    Extract text from every page of a PDF.

    For each page:
    * Try native text via pymupdf.
    * If the native text is shorter than ``ocr_text_threshold`` characters,
      render the page to an image and OCR it (this catches scanned/image-only
      pages). If OCR also yields nothing, keep whatever native text we got
      (possibly empty) rather than dropping the page.

    Returns a list of :class:`Page` in page order (1-based ``page_no``).
    """
    try:
        import fitz  # lazy import so the module is importable without pymupdf
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("pymupdf is required for PDF extraction.") from exc

    engine = ocr_engine or NoOpOCREngine()

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[Page] = []
    try:
        for i in range(len(doc)):
            page = doc.load_page(i)
            native = (page.get_text() or "").strip()
            if len(native) >= ocr_text_threshold:
                pages.append(Page(page_no=i + 1, text=native, source="text"))
                continue

            # Little/no native text -> likely scanned. Try OCR.
            try:
                img = _render_page_to_png(page, dpi=dpi)
                ocr_text = (engine.ocr_image(img) or "").strip()
            except Exception as exc:  # OCR failure must not abort the whole PDF
                logger.warning("OCR failed on page %d: %s", i + 1, exc)
                ocr_text = ""

            if ocr_text:
                pages.append(Page(page_no=i + 1, text=ocr_text, source="ocr"))
            else:
                # No OCR text either: keep native (even if empty) for completeness.
                pages.append(Page(page_no=i + 1, text=native, source="ocr" if ocr_text else "text"))
    finally:
        doc.close()

    return pages
