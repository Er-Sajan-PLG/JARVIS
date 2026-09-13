"""Unit tests for OCR service and OCR package in app/integrations/ocr/."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.integrations.ocr
from app.integrations.ocr.backends.base import OCRResult
from app.integrations.ocr.schemas import (
    OCRBackend as OCRBackendEnum,
    OCRRequest,
    PaddleMode,
    UnlimitedOCRMode,
)
from app.integrations.ocr.service import (
    OCRService,
    OCRServiceError,
    get_ocr_service,
)


def test_ocr_package_init():
    """Verify app.integrations.ocr exports."""
    assert "OCRService" in app.integrations.ocr.__all__
    assert "get_ocr_service" in app.integrations.ocr.__all__
    assert app.integrations.ocr.OCRService is OCRService
    assert app.integrations.ocr.get_ocr_service is get_ocr_service


@pytest.fixture
def service():
    """Create an OCRService instance with mocked model manager."""
    with patch("app.integrations.ocr.service.get_model_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr_getter.return_value = mock_mgr
        svc = OCRService()
        svc.manager = mock_mgr
        yield svc
        svc.shutdown()


@pytest.mark.asyncio
async def test_prepare_images_pdf_success(service):
    """Verify _prepare_images with a valid PDF."""
    with (
        patch("app.integrations.ocr.service.is_pdf", return_value=True),
        patch(
            "app.integrations.ocr.service.get_image_paths",
            return_value=["/tmp/p1.png", "/tmp/p2.png"],
        ),
    ):
        imgs = await service._prepare_images("/tmp/test.pdf", dpi=150)
        assert imgs == ["/tmp/p1.png", "/tmp/p2.png"]


@pytest.mark.asyncio
async def test_prepare_images_pdf_empty_pages(service):
    """Verify _prepare_images with PDF producing no pages raises OCRServiceError."""
    with (
        patch("app.integrations.ocr.service.is_pdf", return_value=True),
        patch("app.integrations.ocr.service.get_image_paths", return_value=[]),
        pytest.raises(OCRServiceError, match="No pages extracted"),
    ):
        await service._prepare_images("/tmp/empty.pdf", dpi=300)


@pytest.mark.asyncio
async def test_prepare_images_valid_image(service):
    """Verify _prepare_images with a valid image file."""
    with (
        patch("app.integrations.ocr.service.is_pdf", return_value=False),
        patch("app.integrations.ocr.service.validate_image", return_value=(True, None)),
    ):
        imgs = await service._prepare_images("/tmp/photo.png", dpi=300)
        assert imgs == ["/tmp/photo.png"]


@pytest.mark.asyncio
async def test_prepare_images_invalid_image(service):
    """Verify _prepare_images with an invalid image raises OCRServiceError."""
    with (
        patch("app.integrations.ocr.service.is_pdf", return_value=False),
        patch(
            "app.integrations.ocr.service.validate_image",
            return_value=(False, "Corrupted image file"),
        ),
        pytest.raises(OCRServiceError, match="Invalid image: Corrupted image file"),
    ):
        await service._prepare_images("/tmp/corrupt.png", dpi=300)


@pytest.mark.asyncio
async def test_run_inference_unlimited(service):
    """Verify _run_inference dispatches unlimited-specific kwargs."""
    mock_backend = MagicMock()
    mock_backend.name = "unlimited"
    expected_result = OCRResult(markdown="result markdown", pages_processed=1)
    mock_backend.process.return_value = expected_result

    req = OCRRequest(
        backend=OCRBackendEnum.UNLIMITED,
        mode=UnlimitedOCRMode.BASE,
        prompt="my prompt",
        ngram_window=64,
        max_tokens=500,
    )

    result = await service._run_inference(mock_backend, ["/tmp/img.png"], req)
    assert result is expected_result
    mock_backend.process.assert_called_once_with(
        ["/tmp/img.png"],
        mode="base",
        prompt="my prompt",
        ngram_window=64,
        max_tokens=500,
    )


@pytest.mark.asyncio
async def test_run_inference_paddle(service):
    """Verify _run_inference dispatches paddle-specific kwargs."""
    mock_backend = MagicMock()
    mock_backend.name = "paddle"
    expected_result = OCRResult(markdown="paddle markdown", pages_processed=1)
    mock_backend.process.return_value = expected_result

    req = OCRRequest(
        backend=OCRBackendEnum.PADDLE,
        paddle_mode=PaddleMode.STRUCTURE,
    )

    result = await service._run_inference(mock_backend, ["/tmp/table.png"], req)
    assert result is expected_result
    mock_backend.process.assert_called_once_with(
        ["/tmp/table.png"],
        paddle_mode="structure",
    )


@pytest.mark.asyncio
async def test_process_upload_success(service):
    """Verify end-to-end process_upload success path."""
    mock_backend = MagicMock()
    mock_backend.name = "unlimited"
    ocr_result = OCRResult(markdown="# Test\nContent", pages_processed=1)
    mock_backend.process.return_value = ocr_result

    service.manager.get_backend.return_value = mock_backend

    with patch.object(service, "_prepare_images", new_callable=AsyncMock) as mock_prep:
        mock_prep.return_value = ["/tmp/page1.png"]
        req = OCRRequest()
        res = await service.process_upload("/tmp/doc.pdf", req)

        assert res.markdown == "# Test\nContent"
        assert res.pages_processed == 1
        assert hasattr(res, "processing_time_seconds")
        assert res.processing_time_seconds >= 0.0


@pytest.mark.asyncio
async def test_process_upload_inference_failure(service):
    """Verify process_upload wraps backend exceptions in OCRServiceError."""
    mock_backend = MagicMock()
    mock_backend.name = "paddle"
    mock_backend.process.side_effect = RuntimeError("GPU out of memory")

    service.manager.get_backend.return_value = mock_backend

    with patch.object(service, "_prepare_images", new_callable=AsyncMock) as mock_prep:
        mock_prep.return_value = ["/tmp/img.png"]
        req = OCRRequest(backend=OCRBackendEnum.PADDLE)

        with pytest.raises(OCRServiceError, match="Inference failed: GPU out of memory"):
            await service.process_upload("/tmp/img.png", req)


@pytest.mark.asyncio
async def test_health_check_healthy(service):
    """Verify health_check when backend model is loaded."""
    service.manager.get_status.return_value = {
        "current_backend": "unlimited",
        "backends": {"unlimited": {"loaded": True, "device": "cuda:0"}},
    }

    health = await service.health_check()
    assert health == {
        "status": "healthy",
        "backend": "unlimited",
        "model_loaded": True,
        "device": "cuda:0",
    }


@pytest.mark.asyncio
async def test_health_check_loading(service):
    """Verify health_check when backend model is not loaded."""
    service.manager.get_status.return_value = {
        "current_backend": "paddle",
        "backends": {"paddle": {"loaded": False, "device": "cpu"}},
    }

    health = await service.health_check()
    assert health == {
        "status": "loading",
        "backend": "paddle",
        "model_loaded": False,
        "device": "cpu",
    }


def test_get_ocr_service_singleton():
    """Verify get_ocr_service returns singleton instance."""
    import app.integrations.ocr.service as svc_mod

    svc_mod._ocr_service = None

    s1 = get_ocr_service()
    s2 = get_ocr_service()
    assert s1 is s2
    assert isinstance(s1, OCRService)
    s1.shutdown()
    svc_mod._ocr_service = None
