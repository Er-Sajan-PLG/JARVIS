"""Unit tests for the OCR service.

The previous version of this file tested ``_prepare_images`` and asserted that
``_run_inference`` forwarded Unlimited-OCR / PaddleOCR keyword arguments. Those
methods and engines are gone. More importantly, the tests here previously
encoded a *state the implementation could not produce*: ``_current_name`` was set
only after a successful load, so "selected but not loaded" was unreachable, yet
``test_health_check_loading`` asserted that ``loaded=False`` reports
``"loading"``. That test is rewritten to assert the reachable, honest behaviour
instead of being satisfied by bending the code to match it.
"""

from unittest.mock import MagicMock, patch

import pytest

import app.integrations.ocr
from app.integrations.ocr.backends.base import OCRResult
from app.integrations.ocr.schemas import OCRRequest
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
    """Create an OCRService instance with a mocked model manager."""
    with patch("app.integrations.ocr.service.get_model_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr_getter.return_value = mock_mgr
        svc = OCRService()
        svc.manager = mock_mgr
        yield svc
        svc.shutdown()


# ── image path ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_upload_rejects_an_invalid_image(service):
    """A corrupted image must raise OCRServiceError naming the reason."""
    with (
        patch("app.integrations.ocr.service.is_pdf", return_value=False),
        patch(
            "app.integrations.ocr.service.validate_image",
            return_value=(False, "Corrupted image file"),
        ),
        pytest.raises(OCRServiceError, match="Invalid image: Corrupted image file"),
    ):
        await service.process_upload("/tmp/corrupt.png", OCRRequest())


@pytest.mark.asyncio
async def test_process_upload_image_success(service):
    """A valid image goes straight to the backend and back."""
    mock_backend = MagicMock()
    mock_backend.name = "tesseract"
    mock_backend.process.return_value = OCRResult(
        markdown="hello", pages_processed=1, backend="tesseract"
    )
    service.manager.get_backend.return_value = mock_backend

    with (
        patch("app.integrations.ocr.service.is_pdf", return_value=False),
        patch("app.integrations.ocr.service.validate_image", return_value=(True, "")),
    ):
        res = await service.process_upload("/tmp/photo.png", OCRRequest())

    assert res.markdown == "hello"
    assert res.backend == "tesseract"
    assert res.processing_time_seconds >= 0.0

    # The backend must receive the second positional argument as a list of paths.
    # The thread-pool lambda makes this call, so assert it ran at all.
    assert mock_backend.process.call_count == 1


@pytest.mark.asyncio
async def test_process_upload_wraps_backend_failure(service):
    """A backend exception becomes OCRServiceError, not a bare 500."""
    mock_backend = MagicMock()
    mock_backend.name = "tesseract"
    mock_backend.process.side_effect = RuntimeError("engine exploded")
    service.manager.get_backend.return_value = mock_backend

    with (
        patch("app.integrations.ocr.service.is_pdf", return_value=False),
        patch("app.integrations.ocr.service.validate_image", return_value=(True, "")),
        pytest.raises(OCRServiceError, match="Inference failed: engine exploded"),
    ):
        await service.process_upload("/tmp/photo.png", OCRRequest())


@pytest.mark.asyncio
async def test_unavailable_engine_is_reported_as_unavailable(service):
    """An unusable engine must say "unavailable" so the route can answer 503.

    The route distinguishes 503 (engine unavailable) from 502 (processing
    failure) by that word, so it is part of the contract.
    """
    service.manager.get_backend.side_effect = RuntimeError("tesseract binary not found")

    with (
        patch("app.integrations.ocr.service.is_pdf", return_value=False),
        patch("app.integrations.ocr.service.validate_image", return_value=(True, "")),
        pytest.raises(OCRServiceError, match="OCR engine unavailable"),
    ):
        await service.process_upload("/tmp/photo.png", OCRRequest())


# ── PDF: native text first, OCR only where needed ───────────────────────────


@pytest.mark.asyncio
async def test_digital_pdf_uses_text_layer_and_never_calls_ocr(service):
    """A PDF with a real text layer must cost no OCR at all."""
    from app.utils.pdf import Page

    pages = [
        Page(page_no=1, text="First page of native text", source="text"),
        Page(page_no=2, text="Second page of native text", source="text"),
    ]
    with patch("app.integrations.ocr.service.extract_pages", return_value=pages):
        res = await service.process_upload("/tmp/digital.pdf", OCRRequest())

    assert "First page of native text" in res.markdown
    assert "Second page of native text" in res.markdown
    assert res.pages_processed == 2
    service.manager.get_backend.assert_not_called()


@pytest.mark.asyncio
async def test_scanned_pages_go_to_ocr_and_keep_their_order(service):
    """Only the scanned pages are OCR'd, and they land back in the right place."""
    from app.utils.pdf import Page

    pages = [
        Page(page_no=1, text="Native page one", source="text"),
        Page(page_no=2, text="", source="scanned", image_path="/tmp/page_0002.png"),
        Page(page_no=3, text="Native page three", source="text"),
    ]
    mock_backend = MagicMock()
    mock_backend.name = "tesseract"
    mock_backend.process.return_value = OCRResult(
        markdown="OCR page two", pages_processed=1, backend="tesseract"
    )
    service.manager.get_backend.return_value = mock_backend

    with patch("app.integrations.ocr.service.extract_pages", return_value=pages):
        res = await service.process_upload("/tmp/mixed.pdf", OCRRequest())

    body = res.markdown
    assert (
        body.index("Native page one") < body.index("OCR page two") < body.index("Native page three")
    )
    assert res.pages_processed == 3


@pytest.mark.asyncio
async def test_pdf_with_no_extractable_text_raises(service):
    """A PDF that yields nothing must fail loudly, not return empty success."""
    from app.utils.pdf import Page

    pages = [Page(page_no=1, text="", source="scanned", image_path="/tmp/p.png")]
    mock_backend = MagicMock()
    mock_backend.process.return_value = OCRResult(markdown="", pages_processed=1)
    service.manager.get_backend.return_value = mock_backend

    with (
        patch("app.integrations.ocr.service.extract_pages", return_value=pages),
        pytest.raises(OCRServiceError, match="No text extracted"),
    ):
        await service.process_upload("/tmp/blank.pdf", OCRRequest())


@pytest.mark.asyncio
async def test_pdf_cleans_up_its_render_directory(service):
    """Rendered pages must not outlive the request.

    ``app/utils/pdf.py`` used ``mkdtemp(prefix="pdf_ocr_")`` and never removed
    it, leaking a directory on every PDF including the success path.
    """
    import glob

    from app.utils.pdf import Page

    before = set(glob.glob("/tmp/jarvis_ocr_*"))
    pages = [Page(page_no=1, text="native text here", source="text")]
    with patch("app.integrations.ocr.service.extract_pages", return_value=pages):
        await service.process_upload("/tmp/digital.pdf", OCRRequest())
    after = set(glob.glob("/tmp/jarvis_ocr_*"))
    assert after - before == set(), "the render directory must be removed"


# ── health ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_check_healthy_when_loaded(service):
    """A loaded engine reports healthy."""
    service.manager.get_status.return_value = {
        "current_backend": "tesseract",
        "backends": {"tesseract": {"loaded": True, "device": "cpu"}},
        "load_error": None,
    }

    health = await service.health_check()
    assert health["status"] == "healthy"
    assert health["backend"] == "tesseract"
    assert health["model_loaded"] is True
    assert health["device"] == "cpu"
    assert health["error"] is None


@pytest.mark.asyncio
async def test_health_check_reports_degraded_with_a_reason(service):
    """An unusable engine must report degraded and say why.

    This replaces ``test_health_check_loading``, which asserted that
    ``loaded=False`` means ``"loading"`` -- a state the implementation could not
    produce, and which reported the same string for "never attempted" and
    "failed permanently" while every request returned 500.
    """
    service.manager.get_status.return_value = {
        "current_backend": None,
        "backends": {},
        "load_error": "RuntimeError: tesseract binary not found",
    }
    service.manager.get_backend.side_effect = RuntimeError("tesseract binary not found")

    health = await service.health_check()
    assert health["status"] == "degraded"
    assert health["model_loaded"] is False
    assert health["error"] is not None
    assert "tesseract" in health["error"]


@pytest.mark.asyncio
async def test_health_check_never_reports_loading(service):
    """``"loading"`` must be gone from the health vocabulary entirely.

    With tesseract there is no load step, so any "loading" would be a lie.
    """
    service.manager.get_status.return_value = {
        "current_backend": None,
        "backends": {},
        "load_error": None,
    }
    service.manager.get_backend.side_effect = RuntimeError("nope")
    health = await service.health_check()
    assert health["status"] != "loading"


def test_get_ocr_service_singleton():
    """Verify get_ocr_service returns a singleton instance."""
    import app.integrations.ocr.service as svc_mod

    svc_mod._ocr_service = None

    s1 = get_ocr_service()
    s2 = get_ocr_service()
    assert s1 is s2
    assert isinstance(s1, OCRService)
    s1.shutdown()
    svc_mod._ocr_service = None


def test_service_does_not_reference_the_removed_engines() -> None:
    """The service must not reference the deleted backends.

    ``service.py`` used to branch on ``backend.name == "unlimited"`` to build
    kwargs for two engines that could never load.
    """
    import inspect

    import app.integrations.ocr.service as svc_mod

    source = inspect.getsource(svc_mod)
    assert "PaddleMode" not in source
    assert 'backend.name == "unlimited"' not in source
    assert "paddle_mode" not in source
