"""JARVIS Integrations Package (Third-Party Open-Source Wrappers).

Isolates external libraries and systems (OCR, ChromaDB vector stores, Git APIs) behind clean JARVIS interfaces.
"""

from app.integrations.ocr import OCRService, get_ocr_service
from app.integrations.vector import ChromaVectorStore

__all__ = [
    "OCRService",
    "get_ocr_service",
    "ChromaVectorStore",
]
