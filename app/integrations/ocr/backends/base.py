"""Base OCR Backend Interface."""

from abc import ABC, abstractmethod

from app.integrations.ocr.schemas import BackendInfo, OCRResult

__all__ = ["OCRBackend", "OCRResult"]


class OCRBackend(ABC):
    """Abstract base class for OCR backends."""

    name: str = "base"

    @abstractmethod
    def load(self) -> None:
        """Prepare the engine for use.

        Must raise ``RuntimeError`` with an actionable message when the engine is
        unusable. It must NOT raise ``AttributeError``: the previous backends
        read a settings attribute that did not exist, and every ``load()`` died
        there.
        """

    @abstractmethod
    def unload(self) -> None:
        """Release engine resources."""

    @abstractmethod
    def is_loaded(self) -> bool:
        """Report whether the engine is ready to serve requests."""

    @abstractmethod
    def process(self, image_paths: list[str], **kwargs: object) -> OCRResult:
        """OCR the given images and return the combined result.

        Blocking; callers must run this in a thread pool, never on the event
        loop.
        """

    @abstractmethod
    def get_info(self) -> BackendInfo:
        """Return engine/device information for health checks.

        Must never raise. A ``get_info()`` that raised is what turned
        ``/api/ocr/health`` into a permanent HTTP 500.
        """
