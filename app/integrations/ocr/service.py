"""OCR Service - High-level document processing."""

import asyncio
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

import structlog

from app.integrations.ocr.backends.tesseract_ocr import _PAGE_SEPARATOR
from app.integrations.ocr.model_manager import get_model_manager
from app.integrations.ocr.schemas import (
    BackendInfo,
    OCRBackend,
    OCRHealth,
    OCRRequest,
    OCRResult,
)
from app.utils.image import validate_image
from app.utils.pdf import extract_pages, is_pdf

log = structlog.get_logger()


class OCRServiceError(Exception):
    """Raised when a document cannot be turned into text."""


class OCRService:
    """Orchestrates document processing: file handling, backend selection, inference."""

    def __init__(self) -> None:
        from app.config.settings import get_settings

        self.settings = get_settings().ocr
        self.manager = get_model_manager()
        self.executor = ThreadPoolExecutor(
            max_workers=self.settings.thread_pool_workers, thread_name_prefix="ocr-worker"
        )

    async def process_upload(self, file_path: str, request: OCRRequest) -> OCRResult:
        """Process an uploaded file (image or PDF)."""
        start_time = time.time()

        if is_pdf(file_path):
            result = await self._process_pdf(file_path, request)
        else:
            valid, err = validate_image(file_path)
            if not valid:
                raise OCRServiceError(f"Invalid image: {err}")
            result = await self._infer(request.backend, [file_path])

        result.processing_time_seconds = round(time.time() - start_time, 2)
        log.info(
            "ocr_completed",
            backend=result.backend,
            pages=result.pages_processed,
            seconds=result.processing_time_seconds,
        )
        return result

    # ── PDF: text layer first, OCR only where needed ────────────────────────

    async def _process_pdf(self, file_path: str, request: OCRRequest) -> OCRResult:
        """Extract a PDF, using its text layer where present and OCR where not.

        The decision is made **per page**, so a digital PDF costs no OCR at all
        and a mostly-digital PDF with a few scanned pages only pays for those
        pages.
        """
        # TemporaryDirectory removes itself, including on the error path. The
        # previous implementation used mkdtemp() and never cleaned up, leaving
        # pdf_ocr_* directories behind on every PDF (success path included).
        with tempfile.TemporaryDirectory(prefix="jarvis_ocr_") as tmp:
            pages = extract_pages(
                file_path,
                dpi=request.dpi,
                native_text_min_chars=self.settings.native_text_min_chars,
                output_dir=tmp,
            )
            if not pages:
                raise OCRServiceError("No pages extracted from document")

            scanned = [p for p in pages if p.source == "scanned" and p.image_path]
            if scanned:
                result = await self._infer(request.backend, [p.image_path or "" for p in scanned])
                blocks = result.markdown.split(_PAGE_SEPARATOR)
                for i, page in enumerate(scanned):
                    if i < len(blocks):
                        page.text = blocks[i]

            markdown = "\n\n".join(p.text.strip() for p in pages if p.text.strip())
            if not markdown:
                raise OCRServiceError("No text extracted from document")

            return OCRResult(
                markdown=markdown,
                pages_processed=len(pages),
                processing_time_seconds=0.0,  # set by caller
                backend="tesseract",
                model_info=f"{len(pages) - len(scanned)} native, {len(scanned)} ocr",
            )

    # ── inference ───────────────────────────────────────────────────────────

    async def _infer(self, requested: OCRBackend, image_paths: list[str]) -> OCRResult:
        """Run backend inference in the thread pool.

        Inference is CPU-bound and blocking, so it must not run on the event
        loop. A timeout is applied: the previous implementation had none, so a
        hung engine occupied one of only two workers forever.
        """
        try:
            backend = self.manager.get_backend(requested)
        except Exception as e:
            # Engine unusable is a service-availability problem, not a crash.
            raise OCRServiceError(f"OCR engine unavailable: {e}") from e

        loop = asyncio.get_running_loop()
        timeout = self.settings.page_timeout_seconds * max(len(image_paths), 1)
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(self.executor, lambda: backend.process(image_paths)),
                timeout=timeout,
            )
        except TimeoutError as e:
            raise OCRServiceError(f"OCR timed out after {timeout}s") from e
        except OCRServiceError:
            raise
        except Exception as e:
            log.error("inference_failed", error=str(e), backend=backend.name)
            raise OCRServiceError(f"Inference failed: {e}") from e

    # ── health ──────────────────────────────────────────────────────────────

    async def health_check(self) -> OCRHealth:
        """Report honestly whether OCR can serve a request.

        The previous version called ``loaded=False`` "loading", which reported
        the same string for "never attempted" and "failed permanently". This
        probes the engine so a cold health response is truthful rather than
        optimistic -- which is what made the old endpoint say healthy while
        every request returned 500.
        """
        status = self.manager.get_status()
        current = status["current_backend"]
        info = status["backends"].get(current or "", BackendInfo())

        if not info.get("loaded"):
            try:
                self.manager.get_backend(OCRBackend.AUTO)
            except Exception as e:
                return {
                    "status": "degraded",
                    "backend": current,
                    "model_loaded": False,
                    "device": "unknown",
                    "error": f"{type(e).__name__}: {e}",
                }
            status = self.manager.get_status()
            current = status["current_backend"]
            info = status["backends"].get(current or "", BackendInfo())

        return {
            "status": "healthy",
            "backend": current,
            "model_loaded": bool(info.get("loaded")),
            "device": info.get("device", "cpu"),
            "error": None,
        }

    def shutdown(self) -> None:
        self.executor.shutdown(wait=True)


_ocr_service: OCRService | None = None


def get_ocr_service() -> OCRService:
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service
