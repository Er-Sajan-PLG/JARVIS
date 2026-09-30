"""Tesseract OCR backend tests.

Written before the backend existed (governance AGENTS.md §1.2 TEST-first).

Why this backend exists
-----------------------
``PaddleOCRBackend`` and ``UnlimitedOCRBackend`` both read ``self.settings.ocr.*``
across 22 call sites, but ``Settings`` (``app/config/settings.py``) never had an
``ocr`` field. Every ``load()`` therefore raised before it could import an engine
or read a weight, and both backends were dead from the day they were written.

Rather than repair two engines that cannot run on this host (no CUDA for
Unlimited-OCR; ``paddleocr`` is not installed and the code targets its 2.x API
while ``requirements.txt`` pins 3.7.0), this backend shells out to the
``tesseract`` binary that is already installed. That choice removes the model
lifecycle entirely: there is no model to load, so there is no multi-minute load,
no lock held across it, and no failed-load state to cache.

These tests assert the *behaviour a caller depends on*, not implementation
details, and each one is written so that it fails if the behaviour regresses.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.integrations.ocr.backends.tesseract_ocr import TesseractBackend

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def text_image(tmp_path: Path) -> str:
    """Render a PNG containing known text, using pymupdf (already a dependency).

    Rendering the fixture rather than committing a binary keeps the test
    hermetic and makes the expected string explicit at the assertion site.
    """
    import pymupdf

    out = tmp_path / "fixture.png"
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=200)
    page.insert_text((40, 110), "TESSERACT FIXTURE 98765", fontsize=26)
    page.get_pixmap(dpi=200).save(str(out))
    doc.close()
    return str(out)


# ── The root cause must be gone ─────────────────────────────────────────────


def test_settings_exposes_an_ocr_section() -> None:
    """``Settings.ocr`` must exist.

    This is the single fact whose absence killed both previous backends. If it
    regresses, every backend fails again with the same AttributeError.
    """
    from app.config.settings import get_settings

    settings = get_settings()
    assert hasattr(settings, "ocr"), (
        "Settings has no 'ocr' section. Both previous OCR backends read "
        "self.settings.ocr.* and died here; see docs/modules/integrations/ocr.md."
    )


def test_ocr_section_declares_english_only_language() -> None:
    """Language is English-only for now, and the default must say so."""
    from app.config.settings import get_settings

    assert get_settings().ocr.language == "eng"


# ── Loading ─────────────────────────────────────────────────────────────────


def test_load_succeeds_without_loading_a_model() -> None:
    """load() verifies the binary, not a model — and must not raise here."""
    backend = TesseractBackend()
    backend.load()
    assert backend.is_loaded() is True


def test_load_is_fast_enough_to_run_on_the_event_loop() -> None:
    """load() must not be a multi-minute blocking operation.

    The previous backends loaded multi-GB models while holding a lock on the
    event loop, freezing the whole HTTP and WebSocket surface. Tesseract has no
    weights, so load() must stay trivial.
    """
    import time

    backend = TesseractBackend()
    start = time.monotonic()
    backend.load()
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"load() took {elapsed:.2f}s; it must not block the event loop"


def test_load_reports_a_clear_error_when_binary_is_missing(monkeypatch) -> None:
    """A missing binary must raise a RuntimeError naming the fix, not AttributeError."""
    monkeypatch.setattr("app.integrations.ocr.backends.tesseract_ocr.shutil.which", lambda _: None)
    backend = TesseractBackend()
    with pytest.raises(RuntimeError, match="tesseract"):
        backend.load()


def test_health_info_states_the_engine_and_device() -> None:
    """get_info() must be truthful and must never raise.

    The previous backends' get_info() raised AttributeError once registered,
    which is what turned /api/ocr/health into a permanent HTTP 500.
    """
    backend = TesseractBackend()
    backend.load()
    info = backend.get_info()
    assert info["loaded"] is True
    assert info["engine"] == "tesseract"
    assert info["device"] == "cpu"
    assert info["language"] == "eng"


# ── Extraction ──────────────────────────────────────────────────────────────


def test_process_extracts_known_text_exactly(text_image: str) -> None:
    """The whole point: text in, that text out."""
    backend = TesseractBackend()
    backend.load()
    result = backend.process([text_image])

    assert result.pages_processed == 1
    assert result.backend == "tesseract"
    normalised = " ".join(result.markdown.split()).upper()
    assert "TESSERACT FIXTURE 98765" in normalised, f"got {result.markdown!r}"


def test_process_before_load_is_an_error_not_a_crash() -> None:
    """Calling process() unloaded must raise a clear error."""
    backend = TesseractBackend()
    with pytest.raises(RuntimeError, match="not loaded"):
        backend.process(["/nonexistent.png"])


def test_process_reports_a_missing_file_clearly() -> None:
    backend = TesseractBackend()
    backend.load()
    with pytest.raises((RuntimeError, FileNotFoundError)):
        backend.process(["/nonexistent/definitely-not-here.png"])


def test_process_handles_multiple_pages_in_order() -> None:
    """pages_processed must reflect the input, and page order must be preserved."""
    import pymupdf

    paths = []
    for n in (1, 2, 3):
        doc = pymupdf.open()
        page = doc.new_page(width=600, height=200)
        page.insert_text((40, 110), f"PAGE NUMBER {n}", fontsize=26)
        p = f"/tmp/ocr_order_{n}.png"
        page.get_pixmap(dpi=200).save(p)
        doc.close()
        paths.append(p)

    backend = TesseractBackend()
    backend.load()
    result = backend.process(paths)
    assert result.pages_processed == 3
    body = result.markdown
    assert body.index("PAGE NUMBER 1") < body.index("PAGE NUMBER 2") < body.index("PAGE NUMBER 3")


def test_process_never_invokes_a_shell(text_image: str) -> None:
    """subprocess must be called with shell disabled.

    This asserts the *behaviour*, not the source text. Asserting on source text
    is a defect this audit found elsewhere in the suite (see
    tests/unit/test_openrouter_max_tokens.py): a comment mentioning the pattern
    would satisfy it. Here the call is intercepted and its arguments inspected.
    """
    captured: list[dict[str, object]] = []
    real_run = subprocess.run

    def spy(cmd, *args, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(dict(kwargs))
        return real_run(cmd, *args, **kwargs)

    import app.integrations.ocr.backends.tesseract_ocr as mod

    original = mod.subprocess.run
    mod.subprocess.run = spy  # type: ignore[assignment]
    backend = TesseractBackend()
    try:
        backend.load()
        captured.clear()  # drop the load-time --version probe
        backend.process([text_image])
    finally:
        mod.subprocess.run = original  # type: ignore[assignment]

    assert captured, "process() must actually invoke tesseract"
    for kwargs in captured:
        assert kwargs.get("shell") is not True, "shell must never be enabled"


def test_process_passes_the_filename_as_an_argv_entry(text_image: str) -> None:
    """The path must be its own argument, never interpolated into a command string."""
    captured: dict[str, list[str]] = {}
    real_run = subprocess.run

    def spy(cmd, *args, **kwargs):  # type: ignore[no-untyped-def]
        captured["cmd"] = list(cmd)
        return real_run(cmd, *args, **kwargs)

    backend = TesseractBackend()
    backend.load()
    import app.integrations.ocr.backends.tesseract_ocr as mod

    original = mod.subprocess.run
    mod.subprocess.run = spy  # type: ignore[assignment]
    try:
        backend.process([text_image])
    finally:
        mod.subprocess.run = original  # type: ignore[assignment]

    cmd = captured["cmd"]
    # The path must be a standalone element (compare basenames: the backend
    # resolves to an absolute path before invoking).
    assert any(
        Path(a).name == Path(text_image).name for a in cmd
    ), f"the file path must appear as its own argv entry, got {cmd!r}"


def test_process_rejects_a_leading_dash_filename(tmp_path: Path) -> None:
    """A filename beginning with '-' must not be read as a tesseract flag.

    The backend resolves to an absolute path, which cannot start with '-'.
    """
    import pymupdf

    dash = tmp_path / "-dash.png"
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=200)
    page.insert_text((40, 110), "DASH FILE 1357", fontsize=26)
    page.get_pixmap(dpi=200).save(str(dash))
    doc.close()

    backend = TesseractBackend()
    backend.load()
    result = backend.process([str(dash)])
    assert "DASH FILE 1357" in " ".join(result.markdown.split()).upper()
