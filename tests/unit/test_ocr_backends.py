"""Unit tests for OCR backends: base, paddle_ocr, and unlimited_ocr."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
import torch

from app.integrations.ocr.backends.base import (
    OCRBackend as BaseOCRBackend,
    OCRResult as BaseOCRResult,
)
from app.integrations.ocr.backends.paddle_ocr import PaddleOCRBackend
from app.integrations.ocr.backends.unlimited_ocr import UnlimitedOCRBackend
from app.integrations.ocr.config import OCRSettings

# =====================================================================
# Base Backend Tests
# =====================================================================


def test_base_ocr_result_dataclass():
    """Verify default and custom BaseOCRResult values."""
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
            super().load()
            self._loaded = True

        def unload(self) -> None:
            super().unload()
            self._loaded = False

        def is_loaded(self) -> bool:
            super().is_loaded()
            return getattr(self, "_loaded", False)

        def process(self, image_paths, **kwargs):
            super().process(image_paths, **kwargs)
            return BaseOCRResult(markdown="done", pages_processed=len(image_paths))

        def get_info(self) -> dict:
            super().get_info()
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


# =====================================================================
# PaddleOCR Backend Tests
# =====================================================================


@pytest.fixture
def mock_paddle_settings(monkeypatch):
    """Ensure settings.ocr exists on the settings singleton."""
    from app.config.settings import get_settings

    settings = get_settings()
    settings.ocr = OCRSettings(
        paddle_lang="en",
        paddle_use_gpu=False,
    )
    return settings


def test_paddle_ocr_init(mock_paddle_settings):
    """Verify PaddleOCRBackend initialization state."""
    backend = PaddleOCRBackend()
    assert backend.name == "paddle"
    assert backend.ocr_engine is None
    assert backend.structure_engine is None
    assert backend.is_loaded() is False
    assert backend.get_info() == {
        "backend": "paddle",
        "lang": "en",
        "gpu": False,
        "loaded": False,
        "structure_available": False,
    }


def test_paddle_ocr_load_missing_dependency(mock_paddle_settings, monkeypatch):
    """Verify load() raises RuntimeError when paddleocr is not installed."""
    backend = PaddleOCRBackend()
    # Ensure paddleocr raises ImportError
    monkeypatch.setitem(sys.modules, "paddleocr", None)
    with pytest.raises(RuntimeError, match="paddleocr not installed"):
        backend.load()


def test_paddle_ocr_load_success(mock_paddle_settings, monkeypatch):
    """Verify load() initializes both ocr and structure engines."""
    mock_paddle_module = ModuleType("paddleocr")
    mock_ocr_cls = MagicMock()
    mock_struct_cls = MagicMock()
    mock_paddle_module.PaddleOCR = mock_ocr_cls
    mock_paddle_module.PPStructureV3 = mock_struct_cls

    monkeypatch.setitem(sys.modules, "paddleocr", mock_paddle_module)

    backend = PaddleOCRBackend()
    backend.load()
    assert backend.is_loaded() is True
    assert backend.ocr_engine is not None
    assert backend.structure_engine is not None
    mock_ocr_cls.assert_called_once_with(
        use_angle_cls=True,
        lang="en",
        use_gpu=False,
        show_log=False,
    )
    mock_struct_cls.assert_called_once_with(
        use_gpu=False,
        show_log=False,
    )

    # Calling load again when already loaded is a no-op
    backend.load()
    assert mock_ocr_cls.call_count == 1

    # Unload
    backend.unload()
    assert backend.is_loaded() is False
    assert backend.ocr_engine is None
    assert backend.structure_engine is None


def test_paddle_ocr_load_structure_failure(mock_paddle_settings, monkeypatch):
    """Verify load() continues if PPStructureV3 raises an exception."""
    mock_paddle_module = ModuleType("paddleocr")
    mock_ocr_cls = MagicMock()
    mock_struct_cls = MagicMock(side_effect=Exception("Structure model error"))
    mock_paddle_module.PaddleOCR = mock_ocr_cls
    mock_paddle_module.PPStructureV3 = mock_struct_cls

    monkeypatch.setitem(sys.modules, "paddleocr", mock_paddle_module)

    backend = PaddleOCRBackend()
    backend.load()
    assert backend.is_loaded() is True
    assert backend.ocr_engine is not None
    assert backend.structure_engine is None
    assert backend.get_info()["structure_available"] is False


def test_paddle_ocr_process_not_loaded(mock_paddle_settings):
    """Verify process() raises RuntimeError when backend is not loaded."""
    backend = PaddleOCRBackend()
    with pytest.raises(RuntimeError, match="PaddleOCR not loaded"):
        backend.process(["/path/to/img.png"])


def test_paddle_ocr_process_ocr_mode(mock_paddle_settings):
    """Verify process() in standard OCR mode."""
    backend = PaddleOCRBackend()
    backend._loaded = True
    backend.ocr_engine = MagicMock()

    # Page 1: 2 boxes, one low confidence (<0.5) to test filtering
    # Page 2: empty page
    page1 = [
        # box: coords, (text, conf)
        [[[0, 10], [10, 10], [10, 20], [0, 20]], ("First Line", 0.95)],
        [[[0, 30], [10, 30], [10, 40], [0, 40]], ("Low Conf Line", 0.3)],
        [[[0, 5], [10, 5], [10, 15], [0, 15]], ("Header Line", 0.99)],
    ]
    page2 = []

    backend.ocr_engine.ocr.return_value = [page1, page2]

    res = backend.process(["img1.png"], paddle_mode="ocr")
    assert res.pages_processed == 1
    assert res.backend == "paddle"
    assert res.model_info == "PaddleOCR (ocr)"
    # Vertical sort: y=5 ("Header Line") before y=10 ("First Line")
    assert res.markdown == "Header Line\nFirst Line"
    assert len(res.json_data) == 1
    assert len(res.json_data[0]["pages"][0]["blocks"]) == 2


def test_paddle_ocr_process_ocr_mode_empty_result(mock_paddle_settings):
    """Verify process() handles empty or None result from engine."""
    backend = PaddleOCRBackend()
    backend._loaded = True
    backend.ocr_engine = MagicMock()
    backend.ocr_engine.ocr.return_value = None

    res = backend.process(["img1.png"])
    assert res.markdown == ""
    assert res.json_data is None


def test_paddle_ocr_process_structure_mode(mock_paddle_settings):
    """Verify process() in PPStructureV3 mode handles text and table regions."""
    backend = PaddleOCRBackend()
    backend._loaded = True
    backend.structure_engine = MagicMock()

    # Mock structure results for 1 image: 1 text region, 1 table region
    page_result = [
        {"type": "text", "bbox": [0, 0, 100, 20], "text": "Document Header"},
        {
            "type": "table",
            "bbox": [0, 30, 100, 100],
            "cells": [
                {"row": 0, "col": 0, "text": "Item"},
                {"row": 0, "col": 1, "text": "Qty | Price"},
                {"row": 1, "col": 0, "text": "Widget"},
                {"row": 1, "col": 1, "text": "10"},
            ],
        },
    ]
    backend.structure_engine.return_value = [page_result]

    res = backend.process(["doc.png"], paddle_mode="structure")
    assert "Document Header" in res.markdown
    assert "| Item | Qty \\| Price |" in res.markdown
    assert "| --- | --- |" in res.markdown
    assert "| Widget | 10 |" in res.markdown
    assert res.json_data is not None
    assert len(res.json_data[0]["pages"][0]["elements"]) == 2


def test_paddle_ocr_table_to_markdown_edge_cases(mock_paddle_settings):
    """Verify _table_to_markdown handles empty cells or rows."""
    backend = PaddleOCRBackend()
    # Empty cells
    assert backend._table_to_markdown({}) == ""
    assert backend._table_to_markdown({"cells": []}) == ""


def test_paddle_ocr_process_structure_mode_fallback(mock_paddle_settings):
    """Verify structure mode falls back to OCR if structure_engine is None."""
    backend = PaddleOCRBackend()
    backend._loaded = True
    backend.structure_engine = None
    backend.ocr_engine = MagicMock()
    backend.ocr_engine.ocr.return_value = [[[[[0, 0]], ("Fallback Text", 0.9)]]]

    res = backend.process(["doc.png"], paddle_mode="structure")
    assert res.markdown == "Fallback Text"


# =====================================================================
# UnlimitedOCR Backend Tests
# =====================================================================


@pytest.fixture
def mock_unlimited_settings():
    """Ensure settings.ocr exists for UnlimitedOCRBackend."""
    from app.config.settings import get_settings

    settings = get_settings()
    settings.ocr = OCRSettings(
        unlimited_model_id="baidu/Unlimited-OCR",
        unlimited_device="cpu",
        unlimited_dtype="bfloat16",
        unlimited_max_length=4096,
        unlimited_trust_remote_code=True,
    )
    return settings


def test_unlimited_ocr_init(mock_unlimited_settings):
    """Verify UnlimitedOCRBackend initialization."""
    backend = UnlimitedOCRBackend()
    assert backend.name == "unlimited"
    assert backend.tokenizer is None
    assert backend.model is None
    assert backend.is_loaded() is False
    assert backend.get_info() == {
        "backend": "unlimited",
        "model": "baidu/Unlimited-OCR",
        "device": "cpu",
        "dtype": "bfloat16",
        "loaded": False,
    }


def test_unlimited_ocr_load_and_unload(mock_unlimited_settings, monkeypatch):
    """Verify UnlimitedOCRBackend load and unload flow."""
    mock_transformers = ModuleType("transformers")
    mock_auto_tokenizer = MagicMock()
    mock_auto_model = MagicMock()
    mock_tokenizer_instance = MagicMock()
    mock_model_instance = MagicMock()

    mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer_instance
    mock_auto_model.from_pretrained.return_value = mock_model_instance
    mock_model_instance.to.return_value = mock_model_instance

    mock_transformers.AutoTokenizer = mock_auto_tokenizer
    mock_transformers.AutoModel = mock_auto_model
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    backend = UnlimitedOCRBackend()
    backend.load()

    assert backend.is_loaded() is True
    assert backend.tokenizer is mock_tokenizer_instance
    assert backend.model is mock_model_instance
    mock_model_instance.to.assert_called_once_with("cpu")
    mock_model_instance.eval.assert_called_once()

    # Second load when already loaded is no-op
    backend.load()
    assert mock_auto_model.from_pretrained.call_count == 1

    # Unload
    with (
        patch("torch.cuda.is_available", return_value=True),
        patch("torch.cuda.empty_cache") as mock_empty_cache,
    ):
        backend.unload()
        assert backend.is_loaded() is False
        assert backend.model is None
        assert backend.tokenizer is None
        mock_empty_cache.assert_called_once()


def test_unlimited_ocr_load_cuda_device(mock_unlimited_settings, monkeypatch):
    """Verify load() with device='cuda' sets device_map='auto'."""
    mock_unlimited_settings.ocr.unlimited_device = "cuda"
    mock_unlimited_settings.ocr.unlimited_dtype = "float16"

    mock_transformers = ModuleType("transformers")
    mock_auto_tokenizer = MagicMock()
    mock_auto_model = MagicMock()
    mock_model_instance = MagicMock()
    mock_auto_model.from_pretrained.return_value = mock_model_instance
    mock_transformers.AutoTokenizer = mock_auto_tokenizer
    mock_transformers.AutoModel = mock_auto_model
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    backend = UnlimitedOCRBackend()
    backend.load()

    mock_auto_model.from_pretrained.assert_called_once_with(
        "baidu/Unlimited-OCR",
        trust_remote_code=True,
        use_safetensors=True,
        torch_dtype=torch.float16,
        device_map="auto",
    )
    mock_model_instance.to.assert_not_called()


def test_unlimited_ocr_process_not_loaded(mock_unlimited_settings):
    """Verify process() raises RuntimeError if model is not loaded."""
    backend = UnlimitedOCRBackend()
    with pytest.raises(RuntimeError, match="Unlimited-OCR model not loaded"):
        backend.process(["/tmp/img.png"])


def test_unlimited_ocr_process_gundam_single(mock_unlimited_settings):
    """Verify single-image gundam mode inference."""
    backend = UnlimitedOCRBackend()
    backend._loaded = True
    backend.tokenizer = MagicMock()
    backend.model = MagicMock()
    backend.model.infer.return_value = "# Extracted Title\nBody text"

    res = backend.process(["img.png"], mode="gundam")
    assert res.markdown == "# Extracted Title\nBody text"
    assert res.pages_processed == 1
    assert res.backend == "unlimited"
    assert "gundam" in res.model_info

    backend.model.infer.assert_called_once_with(
        backend.tokenizer,
        prompt="<image>document parsing.",
        image_file="img.png",
        output_path=None,
        base_size=1024,
        image_size=640,
        crop_mode=True,
        max_length=4096,
        no_repeat_ngram_size=35,
        ngram_window=128,
        save_results=False,
    )


def test_unlimited_ocr_process_base_multi(mock_unlimited_settings):
    """Verify multi-image / base mode inference with custom prompt and parameters."""
    backend = UnlimitedOCRBackend()
    backend._loaded = True
    backend.tokenizer = MagicMock()
    backend.model = MagicMock()
    backend.model.infer_multi.return_value = "Page 1\nPage 2"

    res = backend.process(
        ["p1.png", "p2.png"],
        mode="base",
        prompt="Custom multi prompt",
        ngram_window=512,
        max_tokens=1000,
    )
    assert res.markdown == "Page 1\nPage 2"
    assert res.pages_processed == 2
    assert "base" in res.model_info

    backend.model.infer_multi.assert_called_once_with(
        backend.tokenizer,
        prompt="Custom multi prompt",
        image_files=["p1.png", "p2.png"],
        output_path=None,
        image_size=1024,
        max_length=1000,
        no_repeat_ngram_size=35,
        ngram_window=512,
        save_results=False,
    )


def test_unlimited_ocr_process_non_string_result(mock_unlimited_settings):
    """Verify non-string output from model returns empty string."""
    backend = UnlimitedOCRBackend()
    backend._loaded = True
    backend.tokenizer = MagicMock()
    backend.model = MagicMock()
    backend.model.infer.return_value = None

    res = backend.process(["img.png"], mode="gundam")
    assert res.markdown == ""
