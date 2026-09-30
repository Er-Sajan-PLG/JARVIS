"""Unit tests for OCR Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.integrations.ocr.schemas import (
    BatchOCRRequest,
    HealthResponse,
    OCRBackend,
    OCRRequest,
    OCRResult,
)


def test_ocr_backend_enum_has_only_usable_engines():
    """Verify OCRBackend enum values.

    ``unlimited`` and ``paddle`` were removed because neither could load on the
    target host. This asserts they are *gone*: a caller passing them must get a
    validation error rather than a 500 from a backend that cannot start.
    """
    assert OCRBackend.TESSERACT.value == "tesseract"
    assert OCRBackend.AUTO.value == "auto"
    assert OCRBackend("tesseract") == OCRBackend.TESSERACT
    assert OCRBackend("auto") == OCRBackend.AUTO
    for removed in ("unlimited", "paddle"):
        with pytest.raises(ValueError):
            OCRBackend(removed)
    with pytest.raises(ValueError):
        OCRBackend("nonexistent")


def test_ocr_request_defaults():
    """Verify default values in OCRRequest."""
    req = OCRRequest()
    assert req.backend == OCRBackend.AUTO
    assert req.dpi == 300
    assert req.return_json is False


def test_ocr_request_custom_values():
    """Verify OCRRequest with custom parameters."""
    req = OCRRequest(
        backend=OCRBackend.TESSERACT,
        dpi=150,
        return_json=True,
    )
    assert req.backend == OCRBackend.TESSERACT
    assert req.dpi == 150
    assert req.return_json is True


@pytest.mark.parametrize("dpi", [0, 49, 601, 100000])
def test_ocr_request_rejects_unbounded_dpi(dpi: int) -> None:
    """DPI multiplies a full-page pixmap per page.

    It was previously an unbounded ``Form(...)`` int, which made it a
    memory-exhaustion lever on a 100 MB upload.
    """
    with pytest.raises(ValidationError):
        OCRRequest(dpi=dpi)


def test_ocr_request_removed_engine_options_are_gone():
    """The Unlimited-OCR / PaddleOCR knobs must no longer be accepted."""
    for stale in ("mode", "prompt", "ngram_window", "max_tokens", "paddle_mode"):
        assert stale not in OCRRequest.model_fields, f"{stale} should have been removed"


def test_ocr_result():
    """Verify OCRResult fields and serialization."""
    res = OCRResult(
        markdown="# Title\nText content",
        json_data={"pages": [1]},
        pages_processed=1,
        processing_time_seconds=0.45,
        backend="tesseract",
        model_info="tesseract 5.5.3",
    )
    assert res.markdown == "# Title\nText content"
    assert res.json_data == {"pages": [1]}
    assert res.pages_processed == 1
    assert res.processing_time_seconds == 0.45
    assert res.backend == "tesseract"
    assert res.model_info == "tesseract 5.5.3"

    res_none = OCRResult(
        markdown="simple",
        json_data=None,
        pages_processed=2,
        processing_time_seconds=1.2,
        backend="tesseract",
        model_info="1 native, 1 ocr",
    )
    assert res_none.json_data is None


def test_batch_ocr_request_valid():
    """Verify valid BatchOCRRequest models."""
    req = BatchOCRRequest(files=["/tmp/doc1.pdf", "/tmp/doc2.png"])
    assert req.files == ["/tmp/doc1.pdf", "/tmp/doc2.png"]
    assert req.backend == OCRBackend.AUTO
    assert req.concurrency == 2

    req_custom = BatchOCRRequest(
        files=["/tmp/doc.pdf"],
        backend=OCRBackend.TESSERACT,
        concurrency=8,
    )
    assert req_custom.backend == OCRBackend.TESSERACT
    assert req_custom.concurrency == 8


def test_batch_ocr_request_concurrency_validation():
    """Verify concurrency bounds validation."""
    with pytest.raises(ValidationError):
        BatchOCRRequest(files=["/tmp/doc.pdf"], concurrency=0)

    with pytest.raises(ValidationError):
        BatchOCRRequest(files=["/tmp/doc.pdf"], concurrency=9)


def test_health_response_valid_states():
    """Verify HealthResponse accepts exactly the two reachable states.

    ``"loading"`` was removed: with tesseract there is no load step, and the old
    code used ``"loading"`` for two opposite situations ("never attempted" and
    "failed permanently"). ``"unhealthy"`` was declared but never produced by
    any code path -- it was an unreachable member of the vocabulary.
    """
    for status in ("healthy", "degraded"):
        resp = HealthResponse(
            status=status,
            backend="tesseract",
            model_loaded=True,
            device="cpu",
            version="1.0.0",
        )
        assert resp.status == status
        assert resp.backend == "tesseract"
        assert resp.model_loaded is True
        assert resp.device == "cpu"
        assert resp.version == "1.0.0"


def test_health_response_carries_a_reason_when_degraded() -> None:
    """A degraded health response must say why, so it is actionable."""
    resp = HealthResponse(
        status="degraded",
        backend=None,
        model_loaded=False,
        device="unknown",
        error="RuntimeError: tesseract binary not found",
    )
    assert resp.status == "degraded"
    assert resp.error is not None
    assert "tesseract" in resp.error


def test_health_response_rejects_removed_and_unknown_statuses():
    """Verify neither the removed vocabulary nor an invented value validates."""
    for bad in ("loading", "unhealthy", "offline"):
        with pytest.raises(ValidationError):
            HealthResponse(status=bad, backend="tesseract", model_loaded=False, device="cpu")
