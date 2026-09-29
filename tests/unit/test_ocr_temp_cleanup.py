"""The OCR temp upload directory must not survive a failed request.

`POST /api/ocr/process` created a temp directory, then scheduled
``shutil.rmtree`` as a FastAPI ``BackgroundTasks`` entry. A ``BackgroundTasks``
entry is attached to the **route's response** -- so when the handler raises
``HTTPException``, FastAPI builds a *fresh* response and the cleanup task is
silently dropped.

Net effect: every failure path leaked the entire upload, up to
``max_upload_size_mb`` (default 100 MB), under ``/tmp/jarvis_ocr_*``. The
endpoint has no rate limit, so this is remotely repeatable disk exhaustion, and
the leaked bytes are the user's document.

Cleanup belongs in a ``finally`` block, which runs on every exit path --
including cancellation, where the leaked directory is largest.
"""

from __future__ import annotations

import glob
import os
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.security import API_KEY_ENV
from app.api.ocr.routes import get_service, ocr_router
from app.integrations.ocr.service import OCRServiceError

TEST_KEY = "test-key-temp-cleanup"  # noqa: S105 - fixture value
OCR_TMP_GLOB = "/tmp/jarvis_ocr_*"


def _temp_dirs() -> set[str]:
    return set(glob.glob(OCR_TMP_GLOB))


class _FailingService:
    """Raises on every call; records whether its input file existed."""

    def __init__(self, exc: BaseException) -> None:
        self.exc = exc
        self.saw_path: str | None = None
        self.existed_on_entry = False

    async def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "backend": "stub", "model_loaded": True, "device": "cpu"}

    async def process_upload(self, path: str, request: Any) -> dict[str, Any]:
        self.saw_path = str(path)
        self.existed_on_entry = os.path.exists(path)
        raise self.exc


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV, TEST_KEY)


def _client(service: Any) -> TestClient:
    app = FastAPI()
    app.include_router(ocr_router)
    app.dependency_overrides[get_service] = lambda: service
    # raise_server_exceptions=False so a 500 is returned to us as a response
    # rather than re-raised -- we are asserting on the cleanup, not the error.
    return TestClient(app, raise_server_exceptions=False)


def _post(client: TestClient) -> Any:
    return client.post(
        "/api/ocr/process",
        headers={"Authorization": f"Bearer {TEST_KEY}"},
        files={"file": ("doc.png", b"\x89PNG\r\n\x1a\n" + b"x" * 1024, "image/png")},
    )


def test_tmp_not_leaked_on_happy_path() -> None:
    class OK:
        async def health_check(self) -> dict[str, Any]:
            return {"status": "healthy", "backend": "s", "model_loaded": True, "device": "cpu"}

        async def process_upload(self, path: str, request: Any) -> dict[str, Any]:
            return {
                "markdown": "",
                "pages_processed": 1,
                "processing_time_seconds": 0.0,
                "backend": "stub",
                "model_info": "stub",
            }

    before = _temp_dirs()
    assert _post(_client(OK())).status_code == 200
    assert _temp_dirs() - before == set(), "happy path leaked its temp directory"


def test_tmp_not_leaked_when_service_raises_ocrserviceerror() -> None:
    """The 502 path -- previously the highest-frequency leak."""
    before = _temp_dirs()
    response = _post(_client(_FailingService(OCRServiceError("engine exploded"))))
    leaked = _temp_dirs() - before
    assert response.status_code == 502
    assert leaked == set(), (
        f"502 path leaked {len(leaked)} temp dir(s): {sorted(leaked)}. "
        "BackgroundTasks entries are dropped when the handler raises."
    )


def test_tmp_not_leaked_on_unexpected_exception() -> None:
    """The 500 path."""
    before = _temp_dirs()
    response = _post(_client(_FailingService(RuntimeError("unexpected"))))
    leaked = _temp_dirs() - before
    assert response.status_code == 500
    assert leaked == set(), f"500 path leaked {len(leaked)} temp dir(s): {sorted(leaked)}"


def test_tmp_not_leaked_on_cancellation() -> None:
    """Client disconnect / task cancellation -- the largest leaked payload.

    Mirrors a client going away mid-request, which is exactly when a 100 MB
    upload is most likely to be abandoned.
    """
    import asyncio

    before = _temp_dirs()
    response = _post(_client(_FailingService(asyncio.CancelledError())))
    leaked = _temp_dirs() - before
    assert leaked == set(), f"cancellation path leaked {len(leaked)} temp dir(s): {sorted(leaked)}"
    # CancelledError may surface as 500 through the test transport; the point of
    # this test is the filesystem assertion, not the status code.
    assert response.status_code in (500, 502)


def test_upload_reached_the_service_before_cleanup() -> None:
    """Guard against 'fixing' the leak by deleting the file too early.

    A cleanup fix that removes the directory before the service reads it would
    pass every test above while breaking OCR entirely.
    """
    service = _FailingService(OCRServiceError("boom"))
    _post(_client(service))
    assert service.saw_path is not None, "the service was never called"
    assert service.existed_on_entry is True, (
        "the upload was deleted before the service could read it -- "
        "cleanup must run after the call, not before"
    )
