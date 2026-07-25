"""OCR Service Configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Set, Literal
from functools import lru_cache


class OCRSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Backend selection: "unlimited" | "paddle" | "auto"
    ocr_backend: Literal["unlimited", "paddle", "auto"] = "auto"

    # Unlimited-OCR (Transformers)
    unlimited_model_id: str = "baidu/Unlimited-OCR"
    unlimited_device: str = "cuda"  # "cuda" | "cpu" | "mps"
    unlimited_dtype: str = "bfloat16"  # "bfloat16" | "float16" | "float32"
    unlimited_max_length: int = 32768
    unlimited_trust_remote_code: bool = True

    # PaddleOCR
    paddle_lang: str = "en"
    paddle_use_gpu: bool = True
    paddle_det_model_dir: str = ""
    paddle_rec_model_dir: str = ""

    # Processing
    max_upload_size_mb: int = 100
    pdf_dpi: int = 300
    allowed_extensions: Set[str] = {
        ".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"
    }

    # Thread pool for blocking model inference
    thread_pool_workers: int = 2

    # Timeouts
    request_timeout_seconds: int = 600


@lru_cache()
def get_ocr_settings() -> OCRSettings:
    return OCRSettings()