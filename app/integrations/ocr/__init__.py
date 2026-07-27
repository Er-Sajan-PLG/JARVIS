"""OCR Integration Package.

Wraps third-party OCR backends (PaddleOCR, PyMuPDF, Tesseract) behind clean interfaces.
"""

from app.integrations.ocr.service import OCRService, get_ocr_service

__all__ = ["OCRService", "get_ocr_service"]
