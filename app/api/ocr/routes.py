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
from app.config.settings import get_settings
from app.integrations.ocr.schemas import (
    HealthResponse,
    OCRBackend,
    OCRRequest,
    OCRResult,
)
from app.integrations.ocr.service import OCRService, OCRServiceError, get_ocr_service

log = structlog.get_logger()

# "The engine is not installed / cannot run" is an availability problem, not a
# client error and not a gateway error. The previous code returned 500 with the
# internal exception text in the body, while docs/API_CONTRACT.md promised 502.
_ENGINE_UNAVAILABLE = 503


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


def _check_extension(filename: str) -> str:
    """Return the lowercased extension, or raise 400 if the name is unusable.

    A NUL byte is rejected explicitly. It passes the suffix check (``Path``
    treats it as an ordinary character, so ``"a\\x00.png"`` has suffix ``.png``)
    and then reaches ``open()``, where the OS raises ``ValueError: embedded null
    byte``. That is a malformed request, so it must be a 400 -- previously it
    surfaced as a 500 because a route-wide ``except Exception`` swallowed it.
    """
    if "\x00" in filename:
        raise HTTPException(status_code=400, detail="Filename contains a null byte")

    settings = get_settings().ocr
    ext = Path(filename).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {settings.allowed_extensions}",
        )
    return ext


@ocr_router.get("/health", response_model=HealthResponse)
async def health_check(service: OCRService = Depends(get_service)) -> HealthResponse:
    """Report whether OCR can serve a request.

    Truthful by construction: the engine is probed, so this answers ``degraded``
    with a reason rather than claiming health while every request fails. It must
    never itself return 500 -- a health endpoint that fails instead of reporting
    unhealth is worse than no health endpoint.
    """
    try:
        health = await service.health_check()
    except Exception as e:  # defensive: health must always answer
        log.exception("ocr_health_check_failed")
        health = {
            "status": "degraded",
            "backend": None,
            "model_loaded": False,
            "device": "unknown",
            "error": f"{type(e).__name__}: {e}",
        }
    return HealthResponse(**health)


@ocr_router.post("/process", response_model=OCRResult)
async def process_document(
    file: UploadFile = File(..., description="Image or PDF file"),
    backend: OCRBackend = Form(default=OCRBackend.AUTO, description="OCR engine"),
    dpi: int = Form(default=300, ge=50, le=600, description="PDF render DPI"),
    return_json: bool = Form(default=False, description="Return structured JSON"),
    service: OCRService = Depends(get_service),
) -> OCRResult:
    """Extract text from an uploaded image or PDF.

    **Engines:** ``auto`` (currently the same as ``tesseract``) or ``tesseract``.

    **PDFs** use their embedded text layer where present and OCR only the pages
    that lack one, so a digital PDF costs no OCR at all.

    ``dpi`` is bounded to 50–600: it multiplies a full-page pixmap per page, so
    an unbounded value was a memory-exhaustion lever.
    """
    _check_extension(file.filename or "")

    # Check file size
    file.file.seek(0, 2)
    size_mb = file.file.tell() / (1024 * 1024)
    file.file.seek(0)
    max_mb = get_settings().ocr.max_upload_size_mb
    if size_mb > max_mb:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {size_mb:.1f}MB > {max_mb}MB",
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

        request = OCRRequest(backend=backend, dpi=dpi, return_json=return_json)
        return await service.process_upload(temp_path, request)

    except OCRServiceError as e:
        log.error("ocr_service_error", error=str(e))
        # Engine unavailable is 503; anything else is a genuine gateway failure.
        code = _ENGINE_UNAVAILABLE if "unavailable" in str(e).lower() else 502
        raise HTTPException(code, str(e)) from e
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
    dpi: int = Form(default=300, ge=50, le=600),
    service: OCRService = Depends(get_service),
) -> OCRResult:
    """Process a file already on the server filesystem (for batch/internal use).

    The path is checked against ``allowed_extensions`` exactly as ``/process``
    does. It previously applied no filter at all, so any readable file --
    ``.env``, ``~/.ssh/id_rsa`` -- was handed to the OCR engine and its decoded
    text returned in the response body. That turned an unauthenticated endpoint
    into an arbitrary-file-read primitive.

    Errors are mapped the same way as ``/process``. Previously this endpoint had
    no error handling at all, so an engine failure escaped as a bare 500 with no
    diagnostic and no documented status.
    """
    _check_extension(file_path)

    if not os.path.isfile(file_path):
        raise HTTPException(404, f"File not found: {file_path}")

    request = OCRRequest(backend=backend, dpi=dpi)
    try:
        return await service.process_upload(file_path, request)
    except OCRServiceError as e:
        log.error("ocr_service_error", error=str(e), path=file_path)
        code = _ENGINE_UNAVAILABLE if "unavailable" in str(e).lower() else 502
        raise HTTPException(code, str(e)) from e
