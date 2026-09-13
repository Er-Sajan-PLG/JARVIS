"""Unit tests for OCR settings configuration in app/integrations/ocr/config.py."""

from app.integrations.ocr.config import OCRSettings, get_ocr_settings


def test_ocr_settings_defaults():
    """Verify default values of OCRSettings."""
    settings = OCRSettings()
    assert settings.ocr_backend == "auto"
    assert settings.unlimited_model_id == "baidu/Unlimited-OCR"
    assert settings.unlimited_device == "cuda"
    assert settings.unlimited_dtype == "bfloat16"
    assert settings.unlimited_max_length == 32768
    assert settings.unlimited_trust_remote_code is True
    assert settings.paddle_lang == "en"
    assert settings.paddle_use_gpu is True
    assert settings.paddle_det_model_dir == ""
    assert settings.paddle_rec_model_dir == ""
    assert settings.max_upload_size_mb == 100
    assert settings.pdf_dpi == 300
    assert ".pdf" in settings.allowed_extensions
    assert ".png" in settings.allowed_extensions
    assert ".jpg" in settings.allowed_extensions
    assert settings.thread_pool_workers == 2
    assert settings.request_timeout_seconds == 600


def test_ocr_settings_custom_values():
    """Verify OCRSettings initialization with custom arguments."""
    settings = OCRSettings(
        ocr_backend="unlimited",
        unlimited_model_id="custom/model",
        unlimited_device="cpu",
        unlimited_dtype="float32",
        unlimited_max_length=4096,
        unlimited_trust_remote_code=False,
        paddle_lang="ch",
        paddle_use_gpu=False,
        paddle_det_model_dir="/models/det",
        paddle_rec_model_dir="/models/rec",
        max_upload_size_mb=50,
        pdf_dpi=200,
        allowed_extensions={".png", ".jpg"},
        thread_pool_workers=4,
        request_timeout_seconds=120,
    )
    assert settings.ocr_backend == "unlimited"
    assert settings.unlimited_model_id == "custom/model"
    assert settings.unlimited_device == "cpu"
    assert settings.unlimited_dtype == "float32"
    assert settings.unlimited_max_length == 4096
    assert settings.unlimited_trust_remote_code is False
    assert settings.paddle_lang == "ch"
    assert settings.paddle_use_gpu is False
    assert settings.paddle_det_model_dir == "/models/det"
    assert settings.paddle_rec_model_dir == "/models/rec"
    assert settings.max_upload_size_mb == 50
    assert settings.pdf_dpi == 200
    assert settings.allowed_extensions == {".png", ".jpg"}
    assert settings.thread_pool_workers == 4
    assert settings.request_timeout_seconds == 120


def test_ocr_settings_from_env(monkeypatch):
    """Verify OCRSettings parses values from environment variables."""
    monkeypatch.setenv("OCR_BACKEND", "paddle")
    monkeypatch.setenv("UNLIMITED_DEVICE", "mps")
    monkeypatch.setenv("THREAD_POOL_WORKERS", "8")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "300")

    settings = OCRSettings()
    assert settings.ocr_backend == "paddle"
    assert settings.unlimited_device == "mps"
    assert settings.thread_pool_workers == 8
    assert settings.request_timeout_seconds == 300


def test_get_ocr_settings_caching():
    """Verify get_ocr_settings is cached and returns singleton."""
    get_ocr_settings.cache_clear()
    first = get_ocr_settings()
    second = get_ocr_settings()
    assert first is second
    assert isinstance(first, OCRSettings)
    get_ocr_settings.cache_clear()
