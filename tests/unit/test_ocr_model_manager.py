"""Unit tests for OCR model manager in app/integrations/ocr/model_manager.py."""

from unittest.mock import MagicMock, patch

import pytest

from app.integrations.ocr.model_manager import (
    ModelManager,
    get_model_manager,
    model_lifespan,
)
from app.integrations.ocr.schemas import OCRBackend as OCRBackendEnum


@pytest.fixture
def mock_backend_classes():
    """Mock backend classes created by ModelManager."""
    with (
        patch("app.integrations.ocr.model_manager.UnlimitedOCRBackend") as mock_unlimited_cls,
        patch("app.integrations.ocr.model_manager.PaddleOCRBackend") as mock_paddle_cls,
    ):
        mock_unlimited = MagicMock()
        mock_unlimited.name = "unlimited"
        mock_unlimited.is_loaded.return_value = False
        mock_unlimited.get_info.return_value = {"backend": "unlimited", "loaded": True}
        mock_unlimited_cls.return_value = mock_unlimited

        mock_paddle = MagicMock()
        mock_paddle.name = "paddle"
        mock_paddle.is_loaded.return_value = False
        mock_paddle.get_info.return_value = {"backend": "paddle", "loaded": True}
        mock_paddle_cls.return_value = mock_paddle

        yield {
            "unlimited_cls": mock_unlimited_cls,
            "paddle_cls": mock_paddle_cls,
            "unlimited": mock_unlimited,
            "paddle": mock_paddle,
        }


def test_create_backend_valid_and_invalid(mock_backend_classes):
    """Verify _create_backend instantiates correct backend or raises ValueError."""
    manager = ModelManager()

    unlimited = manager._create_backend("unlimited")
    assert unlimited is mock_backend_classes["unlimited"]

    paddle = manager._create_backend("paddle")
    assert paddle is mock_backend_classes["paddle"]

    with pytest.raises(ValueError, match="Unknown backend: invalid_name"):
        manager._create_backend("invalid_name")


def test_get_backend_auto_selection(mock_backend_classes):
    """Verify AUTO backend picks unlimited when CUDA is available and paddle when not."""
    manager = ModelManager()

    # Case 1: CUDA available -> unlimited
    with patch("torch.cuda.is_available", return_value=True):
        backend = manager.get_backend(OCRBackendEnum.AUTO)
        assert backend is mock_backend_classes["unlimited"]
        backend.load.assert_called_once()
        backend.is_loaded.return_value = True

    # Case 2: CUDA not available -> paddle
    manager2 = ModelManager()
    with patch("torch.cuda.is_available", return_value=False):
        backend2 = manager2.get_backend(OCRBackendEnum.AUTO)
        assert backend2 is mock_backend_classes["paddle"]
        backend2.load.assert_called_once()


def test_get_backend_caching_and_switching(mock_backend_classes):
    """Verify caching of current backend and unloading previous backend on switch."""
    manager = ModelManager()

    unlimited = mock_backend_classes["unlimited"]
    paddle = mock_backend_classes["paddle"]

    # 1. Request unlimited
    b1 = manager.get_backend(OCRBackendEnum.UNLIMITED)
    assert b1 is unlimited
    unlimited.load.assert_called_once()
    unlimited.is_loaded.return_value = True

    # 2. Request unlimited again (should return cached without extra load)
    b2 = manager.get_backend(OCRBackendEnum.UNLIMITED)
    assert b2 is unlimited
    assert unlimited.load.call_count == 1

    # 3. Request paddle (should switch: load paddle, unload unlimited)
    b3 = manager.get_backend(OCRBackendEnum.PADDLE)
    assert b3 is paddle
    paddle.load.assert_called_once()
    paddle.is_loaded.return_value = True
    unlimited.unload.assert_called_once()

    # 4. Status check
    status = manager.get_status()
    assert status["current_backend"] == "paddle"
    assert "paddle" in status["backends"]
    assert "unlimited" in status["backends"]


def test_unload_all(mock_backend_classes):
    """Verify unload_all unloads all loaded backends and resets current."""
    manager = ModelManager()
    unlimited = mock_backend_classes["unlimited"]
    paddle = mock_backend_classes["paddle"]

    unlimited.is_loaded.return_value = True
    paddle.is_loaded.return_value = True
    manager._backends["unlimited"] = unlimited
    manager._backends["paddle"] = paddle
    manager._current_backend = paddle
    manager._current_name = "paddle"

    manager.unload_all()
    unlimited.unload.assert_called_once()
    paddle.unload.assert_called_once()
    assert manager._current_backend is None
    assert manager._current_name is None


def test_get_model_manager_singleton():
    """Verify get_model_manager returns singleton instance."""
    import app.integrations.ocr.model_manager as mm_mod

    mm_mod._model_manager = None

    m1 = get_model_manager()
    m2 = get_model_manager()
    assert m1 is m2
    assert isinstance(m1, ModelManager)


@pytest.mark.asyncio
async def test_model_lifespan(mock_backend_classes):
    """Verify FastAPI lifespan context manager yields and calls unload_all on exit."""
    import app.integrations.ocr.model_manager as mm_mod

    mock_mgr = MagicMock()
    mm_mod._model_manager = mock_mgr

    app_mock = MagicMock()
    async with model_lifespan(app_mock):
        pass

    mock_mgr.unload_all.assert_called_once()
