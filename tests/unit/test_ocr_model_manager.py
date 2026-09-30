"""Unit tests for the OCR model manager.

These tests drive the real ``ModelManager`` against a stubbed backend *class*,
rather than patching the manager's collaborators out of existence. The previous
version patched both backend classes, so its one call to the real
``get_status()`` only ever saw ``MagicMock`` objects and could never observe the
``AttributeError`` that made ``/api/ocr/health`` return 500 in production.

The behaviour under test is the fix for that class of failure:
**a backend that fails to load must not be registered.**
"""

from unittest.mock import patch

import pytest

from app.integrations.ocr.model_manager import ModelManager, get_model_manager
from app.integrations.ocr.schemas import OCRBackend as OCRBackendEnum


class _StubBackend:
    """A backend whose load() outcome the test controls."""

    name = "tesseract"

    def __init__(self, *, fail_load: bool = False, fail_info: bool = False) -> None:
        self.fail_load = fail_load
        self.fail_info = fail_info
        self._loaded = False
        self.load_calls = 0

    def load(self) -> None:
        self.load_calls += 1
        if self.fail_load:
            raise RuntimeError("stub engine unavailable")
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def process(self, image_paths, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def get_info(self) -> dict:
        if self.fail_info:
            raise AttributeError("'Settings' object has no attribute 'ocr'")
        return {"loaded": self._loaded, "engine": "tesseract", "device": "cpu"}


def test_create_backend_returns_tesseract_and_rejects_unknown():
    """Verify _create_backend instantiates the real backend or raises ValueError."""
    manager = ModelManager()
    backend = manager._create_backend("tesseract")
    assert backend.name == "tesseract"

    with pytest.raises(ValueError, match="Unknown backend: invalid_name"):
        manager._create_backend("invalid_name")


def test_get_backend_loads_and_caches():
    """A second request must reuse the loaded backend, not reload it."""
    stub = _StubBackend()
    manager = ModelManager()
    with patch.object(manager, "_create_backend", return_value=stub):
        b1 = manager.get_backend(OCRBackendEnum.AUTO)
        assert b1 is stub
        assert stub.load_calls == 1
        b2 = manager.get_backend(OCRBackendEnum.AUTO)
        assert b2 is stub
        assert stub.load_calls == 1, "a loaded backend must not be reloaded"


def test_failed_load_does_not_get_registered():
    """THE fix: a backend that fails to load must not be cached.

    Previously the backend was inserted into ``_backends`` *before* ``load()``
    was called, so a raising load stayed registered forever. ``get_status()``
    then called ``get_info()`` on it and raised, which is what turned
    ``/api/ocr/health`` into a permanent HTTP 500 after a single bad request.
    """
    stub = _StubBackend(fail_load=True)
    manager = ModelManager()
    with (
        patch.object(manager, "_create_backend", return_value=stub),
        pytest.raises(RuntimeError, match="stub engine unavailable"),
    ):
        manager.get_backend(OCRBackendEnum.AUTO)

    assert manager.get_status()["backends"] == {}, "a failed backend must not be registered"
    assert manager.get_status()["current_backend"] is None


def test_get_status_stays_answerable_after_a_failed_load():
    """Health must survive a failed load instead of raising.

    This is the regression that produced the permanent 500: build the manager,
    attempt a failing load, then read health twice.
    """
    stub = _StubBackend(fail_load=True)
    manager = ModelManager()
    with (
        patch.object(manager, "_create_backend", return_value=stub),
        pytest.raises(RuntimeError),
    ):
        manager.get_backend(OCRBackendEnum.AUTO)

    first = manager.get_status()
    second = manager.get_status()
    assert first["load_error"] is not None and "unavailable" in first["load_error"]
    assert second == first


def test_get_status_never_raises_even_if_get_info_does():
    """get_info() raising must degrade that entry, not break the endpoint.

    The real historical failure was exactly this: ``get_info()`` raised
    ``AttributeError`` and ``/health`` propagated it as a 500.
    """
    stub = _StubBackend(fail_info=True)
    manager = ModelManager()
    manager._backends["tesseract"] = stub  # type: ignore[assignment]
    manager._current_name = "tesseract"

    status = manager.get_status()
    assert status["backends"]["tesseract"]["loaded"] is False
    assert "error" in status["backends"]["tesseract"]


def test_unload_all_clears_the_registry():
    """unload_all must unload every registered backend and reset current."""
    stub = _StubBackend()
    manager = ModelManager()
    with patch.object(manager, "_create_backend", return_value=stub):
        manager.get_backend(OCRBackendEnum.AUTO)

    manager.unload_all()
    assert manager._current_name is None
    assert manager.get_status()["backends"] == {}
    assert stub.is_loaded() is False


def test_get_model_manager_singleton():
    """Verify get_model_manager returns a singleton instance."""
    import app.integrations.ocr.model_manager as mm_mod

    mm_mod._model_manager = None

    m1 = get_model_manager()
    m2 = get_model_manager()
    assert m1 is m2
    assert isinstance(m1, ModelManager)


def test_manager_does_not_import_torch():
    """ModelManager must not pull in torch.

    ``model_manager.py`` used to ``import torch`` at module scope, on
    ``app.main``'s import path, costing ~774 MB RSS to choose between two
    backends that could not load. Tesseract needs no device selection.
    """
    import inspect

    import app.integrations.ocr.model_manager as mm_mod

    source = inspect.getsource(mm_mod)
    assert "import torch" not in source
    assert "torch.cuda" not in source
