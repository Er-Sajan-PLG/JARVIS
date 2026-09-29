"""Tests for the OCR configuration section.

Replaces the previous ``test_ocr_config.py``, which tested
``app/integrations/ocr/config.py``. That module held a *second* OCR settings
object (a pydantic ``OCRSettings``) that nothing in production ever wrote to,
while the backends read ``Settings.ocr`` -- which did not exist. Two config
systems, one of them unreachable, is root cause #7 of the OCR outage.

The configuration now lives in exactly one place: ``Settings.ocr``
(``app/config/settings.py``). These tests assert **literal** expected values
rather than importing them from the module under test: a test that derives its
expectations from the code it checks cannot detect that code changing, which is
the defect found in ``test_workspace_secret_protection.py:91``.
"""

from __future__ import annotations

from app.config.settings import OCRConfig, get_settings


def test_settings_exposes_ocr_section() -> None:
    """The single fact whose absence broke every backend for two months."""
    assert hasattr(get_settings(), "ocr")


def test_ocr_config_defaults_are_literal() -> None:
    """Defaults are asserted as literals, not read back from the same object."""
    cfg = OCRConfig()
    assert cfg.engine == "tesseract"
    assert cfg.binary_path == "tesseract"
    assert cfg.language == "eng", "language is English-only for now"
    assert cfg.page_timeout_seconds == 120
    assert cfg.native_text_min_chars == 20
    assert cfg.max_upload_size_mb == 100
    assert cfg.thread_pool_workers == 2


def test_ocr_default_extension_allowlist_is_literal() -> None:
    """The allow-list must contain exactly these, pinned here on purpose.

    Writing them out means removing one from the code fails this test, instead
    of silently removing its own test case.
    """
    assert sorted(OCRConfig().allowed_extensions) == [
        ".bmp",
        ".jpeg",
        ".jpg",
        ".pdf",
        ".png",
        ".tif",
        ".tiff",
        ".webp",
    ]


def test_ocr_config_no_longer_carries_the_removed_engines_fields() -> None:
    """The removed engines' settings must be gone, not merely unused.

    ``unlimited_*`` and ``paddle_*`` keys were dead or wrong on this host:
    ``unlimited_device`` defaulted to ``cuda`` with no CUDA present, and
    ``paddle_use_gpu`` defaulted ``True``. Leaving them would invite a future
    reader to think they configure something.
    """
    cfg = OCRConfig()
    for stale in (
        "unlimited_model_id",
        "unlimited_device",
        "unlimited_dtype",
        "unlimited_trust_remote_code",
        "paddle_lang",
        "paddle_use_gpu",
    ):
        assert not hasattr(cfg, stale), f"{stale} should have been removed"


def test_ocr_section_is_the_singleton_settings_object() -> None:
    """Repeated reads return the same object; the section is not rebuilt per call."""
    assert get_settings().ocr is get_settings().ocr
