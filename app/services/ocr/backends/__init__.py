"""Backends Package."""
from app.services.ocr.backends.base import OCRBackend, OCRResult
from app.services.ocr.backends.unlimited_ocr import UnlimitedOCRBackend
from app.services.ocr.backends.paddle_ocr import PaddleOCRBackend

__all__ = ["OCRBackend", "OCRResult", "UnlimitedOCRBackend", "PaddleOCRBackend"]