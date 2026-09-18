"""OCR Service - High-level document processing."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import structlog

from app.integrations.ocr.config import get_ocr_settings
from app.integrations.ocr.model_manager import get_model_manager
from app.integrations.ocr.schemas import OCRRequest, OCRResult
from app.utils.image import validate_image
from app.utils.pdf import get_image_paths, is_pdf

log = structlog.get_logger()


class OCRServiceError(Exception):
    pass


class OCRService:
    """Orchestrates document processing: file handling, backend selection, inference."""

    def __init__(self):
        self.settings = get_ocr_settings()
        self.manager = get_model_manager()
        self.executor = ThreadPoolExecutor(
            max_workers=self.settings.thread_pool_workers, thread_name_prefix="ocr-worker"
        )

    async def process_upload(
        self,
        file_path: str,
        request: OCRRequest,
    ) -> OCRResult:
        """Process uploaded file (image or PDF)."""
        start_time = time.time()

        # Convert to image paths (handles PDF → images)
        image_paths = await self._prepare_images(file_path, request.dpi)

        # Get backend
        backend = self.manager.get_backend(request.backend)

        # Run inference in thread pool
        try:
            result = await self._run_inference(backend, image_paths, request)
        except Exception as e:
            log.error("inference_failed", error=str(e), backend=backend.name)
            raise OCRServiceError(f"Inference failed: {e}")

        elapsed = time.time() - start_time
        result.processing_time_seconds = round(elapsed, 2)

        log.info("ocr_completed", backend=backend.name, pages=result.pages_processed, time=elapsed)

        return result

    async def _prepare_images(self, file_path: str, dpi: int) -> list[str]:
        """Convert file to list of image paths."""
        # Validate
        if is_pdf(file_path):
            image_paths = get_image_paths(file_path, dpi=dpi)
        else:
            valid, err = validate_image(file_path)
            if not valid:
                raise OCRServiceError(f"Invalid image: {err}")
            image_paths = [file_path]

        if not image_paths:
            raise OCRServiceError("No pages extracted from document")

        return image_paths

    async def _run_inference(
        self,
        backend,
        image_paths: list[str],
        request: OCRRequest,
    ) -> OCRResult:
        """Run backend inference in thread pool."""
        # Build kwargs based on backend
        if backend.name == "unlimited":
            kwargs = {
                "mode": request.mode.value,
                "prompt": request.prompt,
                "ngram_window": request.ngram_window,
                "max_tokens": request.max_tokens,
            }
        else:  # paddle
            kwargs = {
                "paddle_mode": request.paddle_mode.value,
            }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor, lambda: backend.process(image_paths, **kwargs)
        )

        return result

    async def health_check(self) -> dict:
        status = self.manager.get_status()
        current = status["current_backend"]
        loaded = status["backends"].get(current, {}).get("loaded", False)

        return {
            "status": "healthy" if loaded else "loading",
            "backend": current,
            "model_loaded": loaded,
            "device": status["backends"].get(current, {}).get("device", "unknown"),
        }

    def shutdown(self):
        self.executor.shutdown(wait=True)


# Global instance
_ocr_service = None


def get_ocr_service() -> OCRService:
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service
