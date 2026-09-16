"""OCR Pydantic Schemas."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class OCRBackend(str, Enum):
    UNLIMITED = "unlimited"
    PADDLE = "paddle"
    AUTO = "auto"


class UnlimitedOCRMode(str, Enum):
    GUNDAM = "gundam"  # Single page, high quality
    BASE = "base"  # Multi-page / PDF


class PaddleMode(str, Enum):
    OCR = "ocr"  # Text detection + recognition
    STRUCTURE = "structure"  # Table/layout recognition (PP-StructureV3)


class OCRRequest(BaseModel):
    backend: OCRBackend = Field(default=OCRBackend.AUTO, description="OCR engine")

    # Unlimited-OCR specific
    mode: UnlimitedOCRMode = Field(
        default=UnlimitedOCRMode.GUNDAM, description="Unlimited-OCR mode"
    )
    prompt: str = Field(default="", description="Custom prompt (optional)")
    ngram_window: int = Field(default=0, description="N-gram window (0=auto)")
    max_tokens: int = Field(default=0, description="Max output tokens (0=default)")

    # PaddleOCR specific
    paddle_mode: PaddleMode = Field(default=PaddleMode.OCR, description="PaddleOCR mode")

    # Common
    dpi: int = Field(default=300, description="PDF render DPI")
    return_json: bool = Field(default=False, description="Return structured JSON")


class OCRResult(BaseModel):
    markdown: str
    json_data: Any | None = None
    pages_processed: int
    processing_time_seconds: float
    backend: str
    model_info: str


class BatchOCRRequest(BaseModel):
    files: list[str] = Field(description="Server-side file paths")
    backend: OCRBackend = OCRBackend.AUTO
    concurrency: int = Field(default=2, ge=1, le=8)


class HealthResponse(BaseModel):
    status: Literal["healthy", "loading", "unhealthy"]
    backend: str
    model_loaded: bool
    device: str
    version: str = "1.0.0"
