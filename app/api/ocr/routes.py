"""OCR API Routes."""

import os
import shutil
import tempfile
from pathlib import Path

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from app.adapters.security import is_authorized
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


def _validate_api_key(request: Request) -> bool:
    """Reject an OCR request that presents no valid credential.

    Applied as a router-level dependency, deliberately: this router was mounted
    without one, so on a live ``0.0.0.0`` bind all three endpoints answered
    anonymous callers. Two of them are file primitives, which made the omission
    an arbitrary-read primitive rather than a missing header check.

    ``app.adapters.web.router`` documents this exact failure mode -- "per-route
    decoration is what let this surface sit open" -- after the same mistake left
    chat, settings and the provider catalogue anonymous. The lesson did not
    travel to this router, so the guard is now attached to the ``APIRouter``
    itself and every endpoint added here inherits it by construction.

    The credential is accepted as ``Authorization: Bearer <key>`` or
    ``X-API-Key: <key>``. Query-parameter credentials stay disabled: an OCR URL
    is likely to be pasted or logged. When ``JARVIS_API_KEY`` is unset,
    ``is_authorized`` allows everything, preserving local development.
    """
    authorization = request.headers.get("authorization")
    x_api_key = request.headers.get("x-api-key")
    if is_authorized(authorization=authorization, x_api_key=x_api_key):
        return True
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


ocr_router = APIRouter(
    prefix="/api/ocr",
    tags=["OCR"],
    dependencies=[Depends(_validate_api_key)],
)


def get_service() -> OCRService:
    return get_ocr_service()


@ocr_router.get("/health", response_model=HealthResponse)
async def health_check(service: OCRService = Depends(get_service)):
    """Check OCR service and model health."""
    health = await service.health_check()
    return HealthResponse(**health)


@ocr_router.post("/process", response_model=OCRResult)
async def process_document(
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

    # Save to temp file. ``file.filename`` is client-supplied and was joined
    # verbatim: a name of ``../../x`` escaped ``temp_dir``, and an absolute name
    # (``/etc/cron.d/x``) discarded it entirely, because ``os.path.join`` resets
    # on a leading separator. Reduce it to a basename before use.
    temp_dir = tempfile.mkdtemp(prefix="jarvis_ocr_")
    safe_name = Path(file.filename or "").name or "upload"
    temp_path = os.path.join(temp_dir, safe_name)

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
        return await service.process_upload(temp_path, request)

    except OCRServiceError as e:
        log.error("ocr_service_error", error=str(e))
        raise HTTPException(502, str(e)) from e
    except Exception as e:
        log.exception("processing_failed", filename=file.filename)
        raise HTTPException(500, f"Processing failed: {e}") from e
    finally:
        # Clean up here, NOT via BackgroundTasks.
        #
        # A BackgroundTasks entry is attached to the route's *response*. When the
        # handler raises HTTPException, FastAPI builds a fresh response and the
        # pending task is silently dropped -- so every failure path leaked the
        # entire upload (up to max_upload_size_mb, default 100 MB) under
        # /tmp/jarvis_ocr_*. With no rate limit on this endpoint that is
        # repeatable disk exhaustion, and the leaked bytes are the user's
        # document. A finally block runs on every exit, including cancellation.
        shutil.rmtree(temp_dir, ignore_errors=True)


@ocr_router.post("/process-path", response_model=OCRResult)
async def process_server_path(
    file_path: str = Form(..., description="Server-side file path"),
    backend: OCRBackend = Form(default=OCRBackend.AUTO),
    mode: UnlimitedOCRMode = Form(default=UnlimitedOCRMode.GUNDAM),
    prompt: str = Form(default=""),
    dpi: int = Form(default=300),
    service: OCRService = Depends(get_service),
):
    """Process a file already on the server filesystem (for batch/internal use).

    The path is checked against ``allowed_extensions`` exactly as ``/process``
    does. It previously applied no filter at all, so any readable file --
    ``.env``, ``~/.ssh/id_rsa`` -- was handed to the OCR engine and its decoded
    text returned in the response body. That turned an unauthenticated endpoint
    into an arbitrary-file-read primitive.
    """
    settings = get_ocr_settings()
    ext = Path(file_path).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {settings.allowed_extensions}",
        )

    if not os.path.isfile(file_path):
        raise HTTPException(404, f"File not found: {file_path}")

    request = OCRRequest(
        backend=backend,
        mode=mode,
        prompt=prompt,
        dpi=dpi,
    )

    result = await service.process_upload(file_path, request)
    return result
