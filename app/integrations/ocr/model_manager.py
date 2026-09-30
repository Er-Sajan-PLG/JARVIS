"""OCR Model Manager — backend registry and health.

What changed and why
--------------------
This module used to import ``torch`` at module scope and hold a
``threading.Lock`` across ``backend.load()``, which loaded a multi-GB model on
the event loop. Three defects followed from that design:

1. **A failed load was cached forever.** The backend was inserted into
   ``_backends`` *before* ``load()`` was called, so a raising load stayed
   registered permanently; ``get_status()`` then called ``get_info()`` on it and
   raised, turning ``/api/ocr/health`` into a permanent HTTP 500 after one bad
   request.
2. **Loading blocked the whole server.** The lock was held across a multi-minute
   load on the event loop, freezing every HTTP and WebSocket request.
3. **A state that could not exist was reported.** ``_current_name`` was set only
   *after* a successful load, so "selected but not loaded" was unreachable —
   yet health called ``loaded=False`` "loading".

The engine is now ``tesseract``, a system binary with no weights, so there is
nothing to load. That removes defects 1–3 structurally rather than by patching:
the registry only ever holds *usable* backends, ``load()`` is cheap enough to run
inline, and there is no "loading" state to misreport.

``torch`` is no longer imported here. It cost ~774 MB RSS on ``app.main``'s
import path for an engine that is not used.
"""

from __future__ import annotations

from threading import Lock

import structlog

from app.integrations.ocr.backends import OCRBackend, TesseractBackend
from app.integrations.ocr.schemas import (
    BackendInfo,
    ModelManagerStatus,
    OCRBackend as OCRBackendEnum,
)

log = structlog.get_logger()


class ModelManager:
    """Registry of usable OCR backends, with lazy load and honest status."""

    def __init__(self) -> None:
        from app.config.settings import get_settings

        self.settings = get_settings().ocr
        self._backends: dict[str, OCRBackend] = {}
        self._current_name: str | None = None
        self._load_error: str | None = None
        self._lock = Lock()

    def _create_backend(self, name: str) -> OCRBackend:
        if name in ("tesseract", "auto"):
            return TesseractBackend(self.settings)
        raise ValueError(f"Unknown backend: {name}")

    def get_backend(self, requested: OCRBackendEnum) -> OCRBackend:
        """Return a loaded backend, creating and loading it if needed.

        The lock is held only for registry mutation. With tesseract there is no
        expensive load to serialise; if a future engine needs one, that load must
        happen outside the lock and off the event loop.
        """
        with self._lock:
            backend_name = (
                self.settings.engine if requested == OCRBackendEnum.AUTO else requested.value
            )

            cached = self._backends.get(backend_name)
            if cached is not None and cached.is_loaded():
                self._current_name = backend_name
                return cached

            backend = cached or self._create_backend(backend_name)
            try:
                backend.load()
            except Exception as e:
                # Do NOT register a backend that failed to load. Registering it
                # is what made /health return 500 permanently.
                self._load_error = f"{type(e).__name__}: {e}"
                log.error("ocr_backend_load_failed", backend=backend_name, error=str(e))
                raise

            self._backends[backend_name] = backend
            self._current_name = backend_name
            self._load_error = None
            return backend

    def unload_all(self) -> None:
        with self._lock:
            for name, backend in self._backends.items():
                if backend.is_loaded():
                    log.info("unloading_backend", backend=name)
                    backend.unload()
            self._backends.clear()
            self._current_name = None

    def get_status(self) -> ModelManagerStatus:
        """Health snapshot. Must never raise.

        Only successfully-loaded backends are registered, so ``get_info()``
        cannot raise the way it used to.
        """
        with self._lock:
            backends: dict[str, BackendInfo] = {}
            for name, backend in self._backends.items():
                try:
                    backends[name] = backend.get_info()
                except Exception as e:  # defensive: health must not 500
                    log.error("ocr_backend_info_failed", backend=name, error=str(e))
                    backends[name] = BackendInfo(loaded=False, error=f"{type(e).__name__}: {e}")
            return {
                "current_backend": self._current_name,
                "backends": backends,
                "load_error": self._load_error,
            }


_model_manager: ModelManager | None = None


def get_model_manager() -> ModelManager:
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
