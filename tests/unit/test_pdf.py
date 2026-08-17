import os
from unittest.mock import MagicMock, patch

import pytest
from app.utils.pdf import pdf_to_images, is_pdf, get_image_paths

def test_is_pdf():
    assert is_pdf("test.pdf") is True
    assert is_pdf("test.PDF") is True
    assert is_pdf("test.png") is False
    assert is_pdf("pdf") is False

def test_get_image_paths_non_pdf():
    result = get_image_paths("test.png")
    assert result == ["test.png"]

@patch("app.utils.pdf.pdf_to_images")
def test_get_image_paths_pdf(mock_pdf_to_images):
    mock_pdf_to_images.return_value = ["page_0001.png"]
    result = get_image_paths("test.pdf", dpi=150, temp_dir="/tmp/custom")
    assert result == ["page_0001.png"]
    mock_pdf_to_images.assert_called_once_with("test.pdf", dpi=150, output_dir="/tmp/custom")

@patch("app.utils.pdf.fitz")
def test_pdf_to_images_with_output_dir(mock_fitz, tmp_path):
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_pixmap = MagicMock()

    mock_page.get_pixmap.return_value = mock_pixmap
    # Simulate a document with 2 pages
    mock_doc.__iter__.return_value = iter([mock_page, mock_page])

    mock_fitz.open.return_value = mock_doc

    output_dir = str(tmp_path / "custom_output")

    result = pdf_to_images("test.pdf", dpi=150, output_dir=output_dir)

    mock_fitz.open.assert_called_once_with("test.pdf")
    mock_fitz.Matrix.assert_called_once_with(150 / 72, 150 / 72)

    assert len(result) == 2
    assert result[0] == os.path.join(output_dir, "page_0001.png")
    assert result[1] == os.path.join(output_dir, "page_0002.png")

    assert mock_pixmap.save.call_count == 2
    mock_doc.close.assert_called_once()
    assert os.path.exists(output_dir)

@patch("app.utils.pdf.fitz")
@patch("app.utils.pdf.tempfile.mkdtemp")
def test_pdf_to_images_without_output_dir(mock_mkdtemp, mock_fitz):
    mock_doc = MagicMock()
    # Empty document
    mock_doc.__iter__.return_value = iter([])
    mock_fitz.open.return_value = mock_doc

    mock_mkdtemp.return_value = "/tmp/mocked_temp_dir"

    result = pdf_to_images("test.pdf")

    mock_fitz.open.assert_called_once_with("test.pdf")
    mock_mkdtemp.assert_called_once_with(prefix="pdf_ocr_")

    assert result == []
    mock_doc.close.assert_called_once()
