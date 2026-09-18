"""OCR API Routes."""

import os
import shutil
import tempfile
from pathlib import Path

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.integrations.ocr.config import get_ocr_settings
from app.integrations.ocr.schemas import (
    HealthResponse,
    OCRBackend,
    OCRRequest,
    OCRResult,
    PaddleMode,
    UnlimitedOCRMode,
)
from app.integrations.ocr.service import OCRService, OCRServiceError, get_ocr_service

log = structlog.get_logger()

ocr_router = APIRouter(prefix="/api/ocr", tags=["OCR"])


def get_service() -> OCRService:
    return get_ocr_service()


@ocr_router.get("/health", response_model=HealthResponse)
async def health_check(service: OCRService = Depends(get_service)):
    """Check OCR service and model health."""
    health = await service.health_check()
    return HealthResponse(**health)


@ocr_router.post("/process", response_model=OCRResult)
async def process_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Image or PDF file"),
    backend: OCRBackend = Form(default=OCRBackend.AUTO, description="OCR engine"),
    # Unlimited-OCR options
    mode: UnlimitedOCRMode = Form(
        default=UnlimitedOCRMode.GUNDAM, description="Unlimited-OCR mode"
    ),
    prompt: str = Form(default="", description="Custom prompt (optional)"),
    ngram_window: int = Form(default=0, description="N-gram window (0=auto)"),
    max_tokens: int = Form(default=0, description="Max tokens (0=default)"),
    # PaddleOCR options
    paddle_mode: PaddleMode = Form(default=PaddleMode.OCR, description="PaddleOCR mode"),
    # Common
    dpi: int = Form(default=300, description="PDF render DPI"),
    return_json: bool = Form(default=False, description="Return structured JSON"),
    service: OCRService = Depends(get_service),
):
    """
    Process a document through OCR.

    **Backends:**
    - `auto`: Unlimited-OCR on GPU, PaddleOCR on CPU
    - `unlimited`: Baidu Unlimited-OCR (best for complex docs, tables, formulas)
    - `paddle`: PaddleOCR (fast, good for simple text)

    **Unlimited-OCR Modes:**
    - `gundam`: Single page, high quality (default)
    - `base`: Multi-page / PDF

    **PaddleOCR Modes:**
    - `ocr`: Text detection + recognition
    - `structure`: Table/layout recognition (PP-StructureV3)
    """
    settings = get_ocr_settings()

    # Validate file
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {settings.allowed_extensions}",
        )

    # Check file size
    file.file.seek(0, 2)
    size_mb = file.file.tell() / (1024 * 1024)
    file.file.seek(0)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {size_mb:.1f}MB > {settings.max_upload_size_mb}MB",
        )

    # Save to temp file
    temp_dir = tempfile.mkdtemp(prefix="jarvis_ocr_")
    temp_path = os.path.join(temp_dir, file.filename)

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        log.info(
            "processing_document",
            filename=file.filename,
            size_mb=round(size_mb, 2),
            backend=backend.value,
        )

        # Build request
        request = OCRRequest(
            backend=backend,
            mode=mode,
            prompt=prompt,
            ngram_window=ngram_window,
            max_tokens=max_tokens,
            paddle_mode=paddle_mode,
            dpi=dpi,
            return_json=return_json,
        )

        # Process
        result = await service.process_upload(temp_path, request)

        # Schedule cleanup
        background_tasks.add_task(shutil.rmtree, temp_dir, True)

        return result

    except OCRServiceError as e:
        background_tasks.add_task(shutil.rmtree, temp_dir, True)
        log.error("ocr_service_error", error=str(e))
        raise HTTPException(502, str(e))
    except Exception as e:
        background_tasks.add_task(shutil.rmtree, temp_dir, True)
        log.exception("processing_failed", filename=file.filename)
        raise HTTPException(500, f"Processing failed: {e}")


@ocr_router.post("/process-path", response_model=OCRResult)
async def process_server_path(
    file_path: str = Form(..., description="Server-side file path"),
    backend: OCRBackend = Form(default=OCRBackend.AUTO),
    mode: UnlimitedOCRMode = Form(default=UnlimitedOCRMode.GUNDAM),
    prompt: str = Form(default=""),
    dpi: int = Form(default=300),
    service: OCRService = Depends(get_service),
):
    """Process a file already on the server filesystem (for batch/internal use)."""
    if not os.path.exists(file_path):
        raise HTTPException(404, f"File not found: {file_path}")

    request = OCRRequest(
        backend=backend,
        mode=mode,
        prompt=prompt,
        dpi=dpi,
    )

    result = await service.process_upload(file_path, request)
    return result
