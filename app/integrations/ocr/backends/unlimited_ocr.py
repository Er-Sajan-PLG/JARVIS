"""Unlimited-OCR Backend (Baidu Unlimited-OCR via Transformers)."""

import structlog
import torch

from app.config.settings import get_settings
from app.integrations.ocr.backends.base import OCRBackend, OCRResult

log = structlog.get_logger()


class UnlimitedOCRBackend(OCRBackend):
    name = "unlimited"

    def __init__(self):
        self.settings = get_settings()
        self.tokenizer = None
        self.model = None
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return

        log.info("loading_unlimited_ocr", model=self.settings.ocr.unlimited_model_id)

        # Import here to avoid loading transformers unless needed
        from transformers import AutoModel, AutoTokenizer

        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        torch_dtype = dtype_map.get(self.settings.ocr.unlimited_dtype, torch.bfloat16)

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.settings.ocr.unlimited_model_id,
            trust_remote_code=self.settings.ocr.unlimited_trust_remote_code,
        )

        self.model = AutoModel.from_pretrained(
            self.settings.ocr.unlimited_model_id,
            trust_remote_code=self.settings.ocr.unlimited_trust_remote_code,
            use_safetensors=True,
            torch_dtype=torch_dtype,
            device_map="auto" if self.settings.ocr.unlimited_device == "cuda" else None,
        )

        if self.settings.ocr.unlimited_device != "cuda":
            self.model = self.model.to(self.settings.ocr.unlimited_device)

        self.model.eval()
        self._loaded = True

        log.info(
            "unlimited_ocr_loaded",
            device=self.settings.ocr.unlimited_device,
            dtype=str(torch_dtype),
        )

    def unload(self) -> None:
        if self.model:
            del self.model
            self.model = None
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self._loaded = False
        log.info("unlimited_ocr_unloaded")

    def is_loaded(self) -> bool:
        return self._loaded

    def get_info(self) -> dict:
        return {
            "backend": self.name,
            "model": self.settings.ocr.unlimited_model_id,
            "device": self.settings.ocr.unlimited_device,
            "dtype": self.settings.ocr.unlimited_dtype,
            "loaded": self._loaded,
        }

    def process(
        self,
        image_paths: list[str],
        mode: str = "gundam",
        prompt: str = "",
        ngram_window: int = 0,
        max_tokens: int = 0,
        **kwargs,
    ) -> OCRResult:
        """Blocking inference - run in thread pool."""
        if not self._loaded:
            raise RuntimeError("Unlimited-OCR model not loaded")

        # Determine prompt and params based on mode
        if mode == "base":
            final_prompt = prompt or "<image>Multi page parsing."
            ngram_window = ngram_window or 1024
            base_size, image_size, crop_mode = 1024, 1024, False
        else:  # gundam
            final_prompt = prompt or "<image>document parsing."
            ngram_window = ngram_window or 128
            base_size, image_size, crop_mode = 1024, 640, True

        max_length = max_tokens or self.settings.ocr.unlimited_max_length

        log.info(
            "unlimited_ocr_infer", pages=len(image_paths), mode=mode, ngram_window=ngram_window
        )

        # Single image with gundam mode
        if len(image_paths) == 1 and mode == "gundam":
            result = self.model.infer(
                self.tokenizer,
                prompt=final_prompt,
                image_file=image_paths[0],
                output_path=None,  # Don't save to disk
                base_size=base_size,
                image_size=image_size,
                crop_mode=crop_mode,
                max_length=max_length,
                no_repeat_ngram_size=35,
                ngram_window=ngram_window,
                save_results=False,
            )
            markdown = result if isinstance(result, str) else ""

        # Multi-image / PDF (base mode)
        else:
            result = self.model.infer_multi(
                self.tokenizer,
                prompt=final_prompt,
                image_files=image_paths,
                output_path=None,
                image_size=1024,  # base mode always uses 1024
                max_length=max_length,
                no_repeat_ngram_size=35,
                ngram_window=ngram_window,
                save_results=False,
            )
            markdown = result if isinstance(result, str) else ""

        return OCRResult(
            markdown=markdown,
            pages_processed=len(image_paths),
            backend=self.name,
            model_info=f"{self.settings.ocr.unlimited_model_id} ({mode})",
        )
