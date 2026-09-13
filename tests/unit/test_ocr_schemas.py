"""Unit tests for OCR Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.integrations.ocr.schemas import (
    BatchOCRRequest,
    HealthResponse,
    OCRBackend,
    OCRRequest,
    OCRResult,
    PaddleMode,
    UnlimitedOCRMode,
)


def test_ocr_backend_enum():
    """Verify OCRBackend enum values."""
    assert OCRBackend.UNLIMITED.value == "unlimited"
    assert OCRBackend.PADDLE.value == "paddle"
    assert OCRBackend.AUTO.value == "auto"
    assert OCRBackend("unlimited") == OCRBackend.UNLIMITED
    assert OCRBackend("paddle") == OCRBackend.PADDLE
    assert OCRBackend("auto") == OCRBackend.AUTO
    with pytest.raises(ValueError):
        OCRBackend("nonexistent")


def test_unlimited_ocr_mode_enum():
    """Verify UnlimitedOCRMode enum values."""
    assert UnlimitedOCRMode.GUNDAM.value == "gundam"
    assert UnlimitedOCRMode.BASE.value == "base"
    assert UnlimitedOCRMode("gundam") == UnlimitedOCRMode.GUNDAM
    assert UnlimitedOCRMode("base") == UnlimitedOCRMode.BASE
    with pytest.raises(ValueError):
        UnlimitedOCRMode("invalid_mode")


def test_paddle_mode_enum():
    """Verify PaddleMode enum values."""
    assert PaddleMode.OCR.value == "ocr"
    assert PaddleMode.STRUCTURE.value == "structure"
    assert PaddleMode("ocr") == PaddleMode.OCR
    assert PaddleMode("structure") == PaddleMode.STRUCTURE
    with pytest.raises(ValueError):
        PaddleMode("invalid_paddle_mode")


def test_ocr_request_defaults():
    """Verify default values in OCRRequest."""
    req = OCRRequest()
    assert req.backend == OCRBackend.AUTO
    assert req.mode == UnlimitedOCRMode.GUNDAM
    assert req.prompt == ""
    assert req.ngram_window == 0
    assert req.max_tokens == 0
    assert req.paddle_mode == PaddleMode.OCR
    assert req.dpi == 300
    assert req.return_json is False


def test_ocr_request_custom_values():
    """Verify OCRRequest with custom parameters."""
    req = OCRRequest(
        backend=OCRBackend.UNLIMITED,
        mode=UnlimitedOCRMode.BASE,
        prompt="Extract table",
        ngram_window=512,
        max_tokens=2048,
        paddle_mode=PaddleMode.STRUCTURE,
        dpi=150,
        return_json=True,
    )
    assert req.backend == OCRBackend.UNLIMITED
    assert req.mode == UnlimitedOCRMode.BASE
    assert req.prompt == "Extract table"
    assert req.ngram_window == 512
    assert req.max_tokens == 2048
    assert req.paddle_mode == PaddleMode.STRUCTURE
    assert req.dpi == 150
    assert req.return_json is True


def test_ocr_result():
    """Verify OCRResult fields and serialization."""
    res = OCRResult(
        markdown="# Title\nText content",
        json_data={"pages": [1]},
        pages_processed=1,
        processing_time_seconds=0.45,
        backend="unlimited",
        model_info="baidu/Unlimited-OCR (gundam)",
    )
    assert res.markdown == "# Title\nText content"
    assert res.json_data == {"pages": [1]}
    assert res.pages_processed == 1
    assert res.processing_time_seconds == 0.45
    assert res.backend == "unlimited"
    assert res.model_info == "baidu/Unlimited-OCR (gundam)"

    res_none = OCRResult(
        markdown="simple",
        json_data=None,
        pages_processed=2,
        processing_time_seconds=1.2,
        backend="paddle",
        model_info="PaddleOCR (ocr)",
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
        backend=OCRBackend.PADDLE,
        concurrency=8,
    )
    assert req_custom.backend == OCRBackend.PADDLE
    assert req_custom.concurrency == 8


def test_batch_ocr_request_concurrency_validation():
    """Verify concurrency bounds validation."""
    with pytest.raises(ValidationError):
        BatchOCRRequest(files=["/tmp/doc.pdf"], concurrency=0)

    with pytest.raises(ValidationError):
        BatchOCRRequest(files=["/tmp/doc.pdf"], concurrency=9)


def test_health_response_valid():
    """Verify HealthResponse valid states."""
    for status in ("healthy", "loading", "unhealthy"):
        resp = HealthResponse(
            status=status,
            backend="paddle",
            model_loaded=True,
            device="cuda",
            version="1.0.0",
        )
        assert resp.status == status
        assert resp.backend == "paddle"
        assert resp.model_loaded is True
        assert resp.device == "cuda"
        assert resp.version == "1.0.0"


def test_health_response_invalid_status():
    """Verify invalid status fails HealthResponse validation."""
    with pytest.raises(ValidationError):
        HealthResponse(
            status="offline",
            backend="unlimited",
            model_loaded=False,
            device="cpu",
        )
