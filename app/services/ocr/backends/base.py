"""Base OCR Backend Interface."""
from abc import ABC, abstractmethod
from typing import List, Optional, Any
from dataclasses import dataclass


@dataclass
class OCRResult:
    markdown: str
    json_data: Optional[Any] = None
    pages_processed: int = 1
    backend: str = ""
    model_info: str = ""


class OCRBackend(ABC):
    """Abstract base class for OCR backends."""
    
    name: str = "base"
    
    @abstractmethod
    def load(self) -> None:
        """Load model into memory."""
        pass
    
    @abstractmethod
    def unload(self) -> None:
        """Free model memory."""
        pass
    
    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        pass
    
    @abstractmethod
    def process(
        self,
        image_paths: List[str],
        **kwargs
    ) -> OCRResult:
        """
        Process images and return OCR result.
        Blocking call - should be run in thread pool.
        """
        pass
    
    @abstractmethod
    def get_info(self) -> dict:
        """Return model/device info for health checks."""
        pass