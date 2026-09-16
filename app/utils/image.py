"""Image Utilities."""

from pathlib import Path

from PIL import Image


def validate_image(path: str) -> tuple[bool, str]:
    """Check if file is a valid image."""
    try:
        with Image.open(path) as img:
            img.verify()
        return True, ""
    except Exception as e:
        return False, str(e)


def get_image_info(path: str) -> dict:
    """Get image dimensions and mode."""
    with Image.open(path) as img:
        return {
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "format": img.format,
        }


def is_supported_image(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
