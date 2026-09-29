"""PDF Processing Utilities.

Two extraction paths
--------------------
:func:`extract_pages` picks a path **per page**:

1. **Native text** — the embedded text layer, read directly by PyMuPDF. This is
   fast and exact, and it is what a "digital" PDF (word-processed, LaTeX,
   exported) has. It costs no OCR at all.
2. **OCR** — if a page yields little or no native text it is a scan or a picture
   of text, so the page is rendered to a PNG and handed to the OCR backend.

Deciding per page means a PDF that is 90% digital but has a couple of scanned
appendices only pays the OCR cost on those pages.

``import fitz`` is spelled ``import pymupdf`` here: PyMuPDF renamed the module
and ``fitz`` now emits a deprecation warning on every import.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf

# A page with fewer characters than this in its native layer is treated as
# scanned. Callers normally use ``OCRConfig.native_text_min_chars``.
DEFAULT_NATIVE_TEXT_MIN_CHARS = 20


@dataclass
class Page:
    """One extracted PDF page."""

    page_no: int  # 1-based
    text: str  # extracted text (native, or OCR'd)
    source: str = "text"  # "text" = native layer, "scanned" = needs/used OCR
    image_path: str | None = None  # set when the page was rendered for OCR


def extract_pages(
    pdf_path: str,
    dpi: int = 300,
    native_text_min_chars: int = DEFAULT_NATIVE_TEXT_MIN_CHARS,
    output_dir: str | None = None,
) -> list[Page]:
    """Extract every page of a PDF, reading text directly where possible.

    Rendered pages are written into ``output_dir``; when it is ``None`` a
    directory is created with :func:`tempfile.mkdtemp`. **The caller owns that
    directory and must remove it** — prefer passing a ``TemporaryDirectory``,
    as ``OCRService`` does.
    """
    doc: Any = pymupdf.open(pdf_path)  # type: ignore[no-untyped-call]
    try:
        if output_dir is not None:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        else:
            output_dir = tempfile.mkdtemp(prefix="pdf_ocr_")

        mat: Any = pymupdf.Matrix(dpi / 72, dpi / 72)  # type: ignore[no-untyped-call]
        pages: list[Page] = []

        for i, page in enumerate(doc):
            page_no = i + 1
            try:
                text = page.get_text() or ""
            except Exception:  # a malformed page must not lose the whole document
                text = ""

            if len(text.strip()) >= native_text_min_chars:
                pages.append(Page(page_no=page_no, text=text, source="text"))
                continue

            out_path = os.path.join(output_dir, f"page_{page_no:04d}.png")
            page.get_pixmap(matrix=mat).save(out_path)
            pages.append(Page(page_no=page_no, text="", source="scanned", image_path=out_path))

        return pages
    finally:
        doc.close()


def pdf_to_images(pdf_path: str, dpi: int = 300, output_dir: str | None = None) -> list[str]:
    """Render every PDF page to PNG, returning the image paths.

    Unlike :func:`extract_pages` this never reads the text layer, so it renders
    every page even when the PDF is fully digital.
    """
    doc: Any = pymupdf.open(pdf_path)  # type: ignore[no-untyped-call]
    try:
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="pdf_ocr_")
        else:
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        mat: Any = pymupdf.Matrix(dpi / 72, dpi / 72)  # type: ignore[no-untyped-call]
        image_paths = []
        for i, page in enumerate(doc):
            out_path = os.path.join(output_dir, f"page_{i + 1:04d}.png")
            page.get_pixmap(matrix=mat).save(out_path)
            image_paths.append(out_path)
        return image_paths
    finally:
        doc.close()


def is_pdf(filename: str) -> bool:
    return filename.lower().endswith(".pdf")


def get_image_paths(input_path: str, dpi: int = 300, temp_dir: str | None = None) -> list[str]:
    """Accept an image or a PDF and return a list of image paths."""
    if is_pdf(input_path):
        return pdf_to_images(input_path, dpi=dpi, output_dir=temp_dir)
    return [input_path]
