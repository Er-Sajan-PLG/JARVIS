"""Backends Package."""
from app.integrations.ocr.backends.base import OCRBackend, OCRResult
from app.integrations.ocr.backends.unlimited_ocr import UnlimitedOCRBackend
from app.integrations.ocr.backends.paddle_ocr import PaddleOCRBackend

__all__ = ["OCRBackend", "OCRResult", "UnlimitedOCRBackend", "PaddleOCRBackend"]