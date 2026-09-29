"""Backends Package."""

from app.integrations.ocr.backends.base import OCRBackend, OCRResult
from app.integrations.ocr.backends.tesseract_ocr import TesseractBackend

__all__ = ["OCRBackend", "OCRResult", "TesseractBackend"]
