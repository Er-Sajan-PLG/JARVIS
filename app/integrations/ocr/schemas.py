"""OCR Pydantic Schemas."""

from enum import Enum
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class OCRBackend(str, Enum):
    """Selectable OCR engine.

    ``unlimited`` and ``paddle`` were removed: neither could ever load.
    ``UnlimitedOCRBackend`` required CUDA (absent on the target host), multi-GB
    weights, and ``trust_remote_code=True``; ``PaddleOCRBackend`` depended on an
    uninstalled package whose pinned version is API-incompatible with the code.
    """

    TESSERACT = "tesseract"
    AUTO = "auto"


class OCRRequest(BaseModel):
    backend: OCRBackend = Field(default=OCRBackend.AUTO, description="OCR engine")

    # Common
    dpi: int = Field(default=300, ge=50, le=600, description="PDF render DPI")
    return_json: bool = Field(default=False, description="Return structured JSON")


class OCRResult(BaseModel):
    """Result of an OCR request.

    This is the single ``OCRResult`` type. ``backends/base.py`` used to define a
    second, structurally similar dataclass, so a backend returned one type while
    the service was annotated for the other -- and the dataclass had no
    ``processing_time_seconds`` field at all.
    """

    markdown: str
    json_data: Any | None = None
    # Defaulted to match the dataclass this replaced, so a partially-populated
    # result is still constructible.
    pages_processed: int = 1
    processing_time_seconds: float = 0.0
    backend: str = ""
    model_info: str = ""


class BatchOCRRequest(BaseModel):
    files: list[str] = Field(description="Server-side file paths")
    backend: OCRBackend = OCRBackend.AUTO
    concurrency: int = Field(default=2, ge=1, le=8)


class BackendInfo(TypedDict, total=False):
    """Per-backend health detail, as returned by ``OCRBackend.get_info``."""

    loaded: bool
    engine: str
    device: str
    language: str
    version: str
    available_languages: list[str]
    error: str


class ModelManagerStatus(TypedDict):
    """Shape of ``ModelManager.get_status()``."""

    current_backend: str | None
    backends: dict[str, BackendInfo]
    load_error: str | None


class OCRHealth(TypedDict):
    """The dict shape ``OCRService.health_check`` returns.

    Typed so the route's ``HealthResponse(**health)`` is checked at type level
    rather than failing on an untyped ``dict``.
    """

    status: Literal["healthy", "degraded"]
    backend: str | None
    model_loaded: bool
    device: str
    error: str | None


class HealthResponse(BaseModel):
    """Health of the OCR subsystem.

    ``"loading"`` was removed from the status vocabulary. With tesseract there
    is no load step, and the old code emitted ``"loading"`` for two opposite
    situations ("never attempted" and "failed permanently"), which made it
    useless as a signal. ``"degraded"`` means the engine cannot serve a request
    and ``error`` says why.
    """

    status: Literal["healthy", "degraded"]
    # ``None`` before any backend has been selected. Declared as plain ``str``,
    # it made ``/api/ocr/health`` raise a validation error and answer HTTP 500
    # instead of reporting that OCR was not ready -- a health endpoint that
    # fails rather than reporting unhealth.
    backend: str | None = None
    model_loaded: bool
    device: str
    error: str | None = None
    version: str = "1.0.0"
