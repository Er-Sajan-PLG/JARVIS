"""PDF Processing Utilities."""

import os
import tempfile
from pathlib import Path

import fitz  # PyMuPDF


def pdf_to_images(pdf_path: str, dpi: int = 300, output_dir: str | None = None) -> list[str]:
    """Convert PDF pages to PNG images. Returns list of image paths."""
    doc = fitz.open(pdf_path)

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="pdf_ocr_")
    else:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    mat = fitz.Matrix(dpi / 72, dpi / 72)
    image_paths = []

    for i, page in enumerate(doc):
        page_num = i + 1
        out_name = f"page_{page_num:04d}.png"
        out_path = os.path.join(output_dir, out_name)
        page.get_pixmap(matrix=mat).save(out_path)
        image_paths.append(out_path)

    doc.close()
    return image_paths


def is_pdf(filename: str) -> bool:
    return filename.lower().endswith(".pdf")


def get_image_paths(input_path: str, dpi: int = 300, temp_dir: str | None = None) -> list[str]:
    """Accept image or PDF, return list of image paths."""
    if is_pdf(input_path):
        return pdf_to_images(input_path, dpi=dpi, output_dir=temp_dir)
    else:
        return [input_path]
