import pytest
from PIL import Image
from app.utils.image import validate_image

def test_validate_image_valid(tmp_path):
    img_path = tmp_path / "test.png"
    img = Image.new("RGB", (10, 10), color="red")
    img.save(img_path)

    is_valid, msg = validate_image(str(img_path))
    assert is_valid is True
    assert msg == ""

def test_validate_image_invalid(tmp_path):
    txt_path = tmp_path / "test.txt"
    txt_path.write_text("This is not an image.")

    is_valid, msg = validate_image(str(txt_path))
    assert is_valid is False
    assert msg != ""

def test_validate_image_missing(tmp_path):
    missing_path = tmp_path / "missing.jpg"

    is_valid, msg = validate_image(str(missing_path))
    assert is_valid is False
    assert msg != ""
