"""Base OCR Backend Interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class OCRResult:
    markdown: str
    json_data: Any | None = None
    pages_processed: int = 1
    backend: str = ""
    model_info: str = ""


class OCRBackend(ABC):
    """Abstract base class for OCR backends."""

    name: str = "base"

    @abstractmethod
    def load(self) -> None:
        """Load model into memory."""

    @abstractmethod
    def unload(self) -> None:
        """Free model memory."""

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if model is loaded."""

    @abstractmethod
    def process(self, image_paths: list[str], **kwargs) -> OCRResult:
        """
        Process images and return OCR result.
        Blocking call - should be run in thread pool.
        """

    @abstractmethod
    def get_info(self) -> dict:
        """Return model/device info for health checks."""
