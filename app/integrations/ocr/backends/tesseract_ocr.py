"""Tesseract OCR backend.

Why this engine
---------------
The two previous backends could not run on this host, for different reasons:
``UnlimitedOCRBackend`` needs CUDA (this machine has none), multi-GB weights, and
the uninstalled ``accelerate``, and it loads with ``trust_remote_code=True``,
which executes Hub-supplied Python; ``PaddleOCRBackend`` depends on a package
that is not installed and whose pinned version (3.7.0) is API-incompatible with
the code, which was written against PaddleOCR 2.x.

``tesseract`` is already installed as a system binary. It needs no download, no
GPU, and no model lifecycle — which is the important part, because the absence of
a load step is what removes three defects structurally rather than by patching:

* no multi-minute blocking load held under a lock on the event loop;
* no "failed load cached forever" state that poisons the health endpoint;
* no unreachable "selected but not loaded" state to report dishonestly.

Anything about *where text comes from* for a PDF (native text layer vs OCR of a
rendered page) lives in ``app/utils/pdf.py``, not here. This backend's job is one
image in, text out.

Security notes
--------------
Filenames are passed as **argv entries**, never interpolated into a command
string, and ``subprocess`` is never invoked with ``shell=True`` (AGENTS.md §2.1).
The path is resolved to absolute form so it cannot begin with ``-`` and be
mistaken for a flag.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import structlog

from app.integrations.ocr.backends.base import OCRBackend as BaseOCRBackend, OCRResult
from app.integrations.ocr.schemas import BackendInfo

log = structlog.get_logger()

# Separator between rendered pages. Tesseract emits one text blob per image, and
# a caller reading a multi-page PDF needs to be able to tell pages apart.
_PAGE_SEPARATOR = "\n\n---\n\n"


class TesseractBackend(BaseOCRBackend):
    """OCR via the ``tesseract`` system binary (CPU, offline, English)."""

    name = "tesseract"

    def __init__(self, settings: object | None = None) -> None:
        if settings is None:
            from app.config.settings import get_settings

            settings = get_settings().ocr
        self.config = settings
        self._loaded = False
        self._binary: str | None = None
        self._version: str = ""
        self._languages: list[str] = []

    # ── lifecycle ───────────────────────────────────────────────────────────

    def load(self) -> None:
        """Verify the engine is present and the configured language is available.

        There is no model to load, so this must stay trivial — it is called on
        the request path. It raises ``RuntimeError`` (never ``AttributeError``)
        when the engine is unusable, naming the fix.
        """
        binary = getattr(self.config, "binary_path", "tesseract")
        resolved = shutil.which(binary)
        if resolved is None:
            raise RuntimeError(
                f"tesseract binary not found (looked for {binary!r}). "
                "Install it with: sudo apt install tesseract-ocr"
            )

        try:
            version = subprocess.run(
                [resolved, "--version"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as e:
            raise RuntimeError(f"tesseract at {resolved} could not be executed: {e}") from e

        if version.returncode != 0:
            raise RuntimeError(
                f"tesseract --version failed (rc={version.returncode}): {version.stderr.strip()}"
            )

        languages = self._list_languages(resolved)
        wanted = getattr(self.config, "language", "eng")
        missing = [lang for lang in wanted.split("+") if lang and lang not in languages]
        if missing:
            raise RuntimeError(
                f"tesseract language(s) {missing} not installed (available: {languages}). "
                f"Install with: sudo apt install tesseract-ocr-{missing[0]}"
            )

        self._binary = resolved
        self._version = version.stdout.splitlines()[0].strip() if version.stdout else ""
        self._languages = languages
        self._loaded = True
        log.info(
            "tesseract_loaded",
            binary=resolved,
            version=self._version,
            language=wanted,
        )

    def unload(self) -> None:
        """Nothing is held in memory, but the flag must still be honest."""
        self._loaded = False
        self._binary = None
        log.info("tesseract_unloaded")

    def is_loaded(self) -> bool:
        return self._loaded

    # ── introspection ───────────────────────────────────────────────────────

    def _list_languages(self, binary: str) -> list[str]:
        try:
            res = subprocess.run(
                [binary, "--list-langs"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        # The first line is a header ("List of available languages ...").
        return [line.strip() for line in res.stdout.splitlines()[1:] if line.strip()]

    def get_info(self) -> BackendInfo:
        """Health information. Must never raise — a raising ``get_info`` is what
        turned ``/api/ocr/health`` into a permanent HTTP 500 before."""
        return {
            "loaded": self._loaded,
            "engine": "tesseract",
            "device": "cpu",
            "language": getattr(self.config, "language", "eng"),
            "version": self._version or "unknown",
            "available_languages": self._languages,
        }

    # ── inference ───────────────────────────────────────────────────────────

    def process(self, image_paths: list[str], **kwargs: object) -> OCRResult:
        """OCR each image and join the results in page order.

        Blocking, and intended to be run in a thread pool (see ``OCRService``).
        """
        if not self._loaded or self._binary is None:
            raise RuntimeError("TesseractBackend is not loaded; call load() first")
        if not image_paths:
            return OCRResult(markdown="", pages_processed=0, backend=self.name, model_info="")

        timeout = int(getattr(self.config, "page_timeout_seconds", 120))
        language = str(getattr(self.config, "language", "eng"))
        pages: list[str] = []

        for path in image_paths:
            pages.append(self._ocr_one(path, language, timeout))

        return OCRResult(
            markdown=_PAGE_SEPARATOR.join(pages),
            pages_processed=len(pages),
            backend=self.name,
            model_info=self._version or "tesseract",
        )

    def _ocr_one(self, path: str, language: str, timeout: int) -> str:
        """Run tesseract on a single image, returning its text."""
        if not Path(path).is_file():
            raise FileNotFoundError(f"image not found: {path}")

        # Resolve to an absolute path. Tesseract reads its input as the first
        # positional argument, but an absolute path also guarantees the value
        # can never begin with '-' and be mistaken for a flag. (Prefixing with
        # './' is NOT an option: it corrupts an already-absolute path into
        # './/tmp/...', which tesseract cannot read.)
        resolved = str(Path(path).resolve())

        # No '--' terminator: tesseract 5.5.3 rejects it outright with
        # "unknown command line argument '--'".
        argv = [str(self._binary), resolved, "stdout", "-l", language]
        try:
            res = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"tesseract timed out after {timeout}s on {Path(path).name}") from e
        except OSError as e:
            raise RuntimeError(f"tesseract could not be executed: {e}") from e

        if res.returncode != 0:
            detail = (res.stderr or "").strip()[:200]
            raise RuntimeError(
                f"tesseract failed on {Path(path).name} (rc={res.returncode}): {detail}"
            )

        return res.stdout
