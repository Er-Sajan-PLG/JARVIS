"""OCR Model Manager - Lazy loading, switching, cleanup."""
import structlog
import torch
from threading import Lock
from typing import Optional, Dict
from contextlib import asynccontextmanager

from app.services.ocr.backends import OCRBackend, UnlimitedOCRBackend, PaddleOCRBackend
from app.services.ocr.config import get_ocr_settings
from app.services.ocr.schemas import OCRBackend as OCRBackendEnum

log = structlog.get_logger()


class ModelManager:
    """Manages OCR backend lifecycle: lazy loading, switching, cleanup."""
    
    def __init__(self):
        self.settings = get_ocr_settings()
        self._backends: Dict[str, OCRBackend] = {}
        self._current_backend: Optional[OCRBackend] = None
        self._current_name: Optional[str] = None
        self._lock = Lock()
    
    def _create_backend(self, name: str) -> OCRBackend:
        if name == "unlimited":
            return UnlimitedOCRBackend()
        elif name == "paddle":
            return PaddleOCRBackend()
        else:
            raise ValueError(f"Unknown backend: {name}")
    
    def get_backend(self, requested: OCRBackendEnum) -> OCRBackend:
        """Get or create backend, loading if needed."""
        with self._lock:
            # Determine which backend to use
            if requested == OCRBackendEnum.AUTO:
                backend_name = "unlimited" if torch.cuda.is_available() else "paddle"
            else:
                backend_name = requested.value
            
            # Return current if matches and loaded
            if self._current_name == backend_name and self._current_backend:
                if self._current_backend.is_loaded():
                    return self._current_backend
            
            # Get or create backend
            if backend_name not in self._backends:
                self._backends[backend_name] = self._create_backend(backend_name)
            
            backend = self._backends[backend_name]
            
            # Load if needed
            if not backend.is_loaded():
                log.info("loading_backend", backend=backend_name)
                backend.load()
                log.info("backend_loaded", backend=backend_name)
            
            # Unload previous if different (save VRAM)
            if self._current_backend and self._current_backend != backend:
                log.info("unloading_previous_backend", backend=self._current_name)
                self._current_backend.unload()
            
            self._current_backend = backend
            self._current_name = backend_name
            return backend
    
    def unload_all(self) -> None:
        with self._lock:
            for name, backend in self._backends.items():
                if backend.is_loaded():
                    log.info("unloading_backend", backend=name)
                    backend.unload()
            self._current_backend = None
            self._current_name = None
    
    def get_status(self) -> dict:
        with self._lock:
            return {
                "current_backend": self._current_name,
                "backends": {
                    name: backend.get_info() 
                    for name, backend in self._backends.items()
                },
            }


_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager


@asynccontextmanager
async def model_lifespan(app):
    """FastAPI lifespan handler."""
    manager = get_model_manager()
    # Optional: pre-warm default backend
    # manager.get_backend(OCRBackendEnum.AUTO)
    yield
    manager.unload_all()