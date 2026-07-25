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
* ``OCREngine`` is a Protocol; ``UnlimitedOCREngine`` / ``NoOpOCREngine`` are the
  pluggable implementations. Swapping OCR backends does not touch the rest.

Heavy imports (``fitz``) are lazy so this module is safe to import even before
those optional deps are installed.
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


class UnlimitedOCREngine:
    """Wrapper around the external Unlimited-OCR integration.

    Delegates to `app.services.ocr.backends.unlimited_ocr.UnlimitedOCREngine`.
    This indirection keeps the PDF extraction module free of heavyweight
    external imports and provides a single place to adapt integration code.
    """

    def __init__(self, opts: Optional[list[str]] = None, gpu: bool = False):
        try:
            from app.services.ocr.backends.unlimited_ocr import UnlimitedOCREngine as _U
        except Exception as exc:  # pragma: no cover - env dependent
            raise RuntimeError(
                "Unlimited-OCR backend is not available. Install the project "
                "from https://github.com/baidu/Unlimited-OCR and ensure it is importable."
            ) from exc
        self._impl = _U(opts={"langs": opts, "gpu": gpu})

    def ocr_image(self, image_bytes: bytes) -> str:
        return self._impl.ocr_image(image_bytes)


class RemoteOCREngine:
    """Adapter that calls an external HTTP OCR service.

    Expects a JSON reply with a top-level `text` field containing the
    recognized text. The endpoint URL is read from the global settings
    (`knowledge.remote_ocr_url`). Timeouts and network errors raise
    RuntimeError to allow the ingestion code to fall back to NoOp.
    """

    def __init__(self, url: Optional[str] = None, timeout: int = 60):
        # Lazy import of settings to avoid import cycles at module import time
        try:
            from app.config.settings import get_settings
        except Exception:  # pragma: no cover - environment dependent
            get_settings = None
        self._timeout = timeout
        self._url = url
        if not self._url and get_settings:
            try:
                self._url = str(get_settings().knowledge.remote_ocr_url or "")
            except Exception:
                self._url = ""

    def ocr_image(self, image_bytes: bytes) -> str:
        if not self._url:
            raise RuntimeError("Remote OCR URL not configured (knowledge.remote_ocr_url)")
        # Use requests if available, else fallback to urllib
        try:
            import requests
        except Exception:
            requests = None

        if requests:
            try:
                files = {"file": ("page.png", image_bytes, "image/png")}
                resp = requests.post(self._url, files=files, timeout=self._timeout)
                resp.raise_for_status()
                j = resp.json()
                text = j.get("text") if isinstance(j, dict) else None
                return str(text or "")
            except Exception as exc:  # pragma: no cover - network dependent
                raise RuntimeError(f"Remote OCR request failed: {exc}") from exc

        # Fallback to stdlib POST using urllib
        try:
            import mimetypes
            import uuid
            from urllib import request as _request
            boundary = uuid.uuid4().hex
            data = []
            data.append(f"--{boundary}")
            data.append('Content-Disposition: form-data; name="file"; filename="page.png"')
            data.append('Content-Type: image/png')
            data.append("")
            body = b"\r\n".join(part.encode("utf-8") if isinstance(part, str) else part for part in data) + b"\r\n" + image_bytes + b"\r\n"
            tail = (f"--{boundary}--\r\n").encode("utf-8")
            body = body + tail
            req = _request.Request(self._url, data=body)
            req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            req.add_header("Content-Length", str(len(body)))
            with _request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read()
                import json as _json
                j = _json.loads(raw.decode("utf-8", errors="replace"))
                return str(j.get("text") or "")
        except Exception as exc:  # pragma: no cover - network dependent
            raise RuntimeError(f"Remote OCR request failed: {exc}") from exc


def build_ocr_engine(engine_name: str, langs: Optional[list[str]] = None, gpu: bool = False) -> OCREngine:
    """
    Factory for the configured OCR backend.

    ``engine_name`` is taken from ``KnowledgeConfig.ocr_engine``
    ("unlimited" | "remote" | "none").
    Unknown names raise an error so misconfigured OCR backends fail fast.
    """
    name = (engine_name or "none").lower()
    if name == "unlimited":
        return UnlimitedOCREngine(opts=langs, gpu=gpu)
    if name == "remote":
        # langs passed through as url if user provided a direct URL string
        url = None
        if langs and isinstance(langs, list) and len(langs) == 1 and isinstance(langs[0], str):
            url = langs[0]
        return RemoteOCREngine(url=url)
    if name == "none":
        return NoOpOCREngine()
    raise ValueError(
        f"Unknown ocr_engine '{engine_name}'. Supported values: "
        "unlimited, remote, none."
    )


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
