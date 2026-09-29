"""Unit tests for the OCR backend base class.

Previously this file also covered ``PaddleOCRBackend`` and
``UnlimitedOCRBackend``. Those tests passed for two months while the feature was
completely dead, because every one of them either created the missing
``settings.ocr`` attribute itself (``settings.ocr = OCRSettings(...)``) or
patched out the backend classes entirely. They are removed along with the
backends rather than rewritten: ``tests/unit/test_ocr_tesseract_backend.py``
drives a real engine end to end.

What remains here is the abstract interface contract.
"""

import pytest

from app.integrations.ocr.backends.base import (
    OCRBackend as BaseOCRBackend,
    OCRResult as BaseOCRResult,
)


def test_ocr_result_defaults_and_custom_values():
    """Verify default and custom OCRResult values.

    This is the single result type -- backends/base.py used to define a second,
    structurally similar dataclass, so a backend returned one type while the
    service was annotated for the other.
    """
    res = BaseOCRResult(markdown="test text")
    assert res.markdown == "test text"
    assert res.json_data is None
    assert res.pages_processed == 1
    assert res.backend == ""
    assert res.model_info == ""

    res_custom = BaseOCRResult(
        markdown="custom",
        json_data={"k": "v"},
        pages_processed=3,
        backend="custom_backend",
        model_info="v1.0",
    )
    assert res_custom.markdown == "custom"
    assert res_custom.json_data == {"k": "v"}
    assert res_custom.pages_processed == 3
    assert res_custom.backend == "custom_backend"
    assert res_custom.model_info == "v1.0"


def test_base_ocr_backend_abstract():
    """Verify OCRBackend cannot be instantiated without implementing abstract methods."""
    with pytest.raises(TypeError):
        BaseOCRBackend()

    class ConcreteBackend(BaseOCRBackend):
        name = "concrete"

        def load(self) -> None:
            self._loaded = True

        def unload(self) -> None:
            self._loaded = False

        def is_loaded(self) -> bool:
            return getattr(self, "_loaded", False)

        def process(self, image_paths, **kwargs):
            return BaseOCRResult(markdown="done", pages_processed=len(image_paths))

        def get_info(self) -> dict:
            return {"backend": self.name}

    backend = ConcreteBackend()
    assert backend.name == "concrete"
    assert not backend.is_loaded()
    backend.load()
    assert backend.is_loaded()
    res = backend.process(["p1.png", "p2.png"])
    assert res.markdown == "done"
    assert res.pages_processed == 2
    assert backend.get_info() == {"backend": "concrete"}
    backend.unload()
    assert not backend.is_loaded()


def test_tesseract_backend_satisfies_the_interface():
    """The real backend must implement every abstract member."""
    from app.integrations.ocr.backends import TesseractBackend

    backend = TesseractBackend()
    assert isinstance(backend, BaseOCRBackend)
    for member in ("load", "unload", "is_loaded", "process", "get_info"):
        assert callable(getattr(backend, member)), f"{member} must be implemented"
