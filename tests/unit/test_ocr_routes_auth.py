"""Auth and path-safety tests for the OCR router (F-TOOL-004 / F-SEC-002).

The OCR router was mounted without a router-level credential dependency, unlike
every sibling router. On a live ``0.0.0.0`` bind that left three endpoints
anonymous, two of which are file primitives:

* ``POST /api/ocr/process`` joined the client-supplied ``UploadFile.filename``
  onto a temp directory, so ``../`` escaped it.
* ``POST /api/ocr/process-path`` OCR'd *any* server-side path and returned its
  text, with no extension filter -- reading ``.env`` or ``~/.ssh/id_rsa``.

These tests assert the contract, not the implementation: an anonymous request is
rejected, an authenticated one is not, and a traversal filename cannot escape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.security import API_KEY_ENV
from app.api.ocr.routes import get_service, ocr_router

TEST_KEY = "test-key-ocr-auth"  # noqa: S105 - fixture value, not a real credential


class _StubService:
    """Records what the route handed the service; never loads a model.

    Payloads satisfy ``HealthResponse`` and ``OCRResult`` so a failing assertion
    can only mean the auth or path-safety contract broke -- never that the stub
    returned a shape the response model rejected.
    """

    def __init__(self) -> None:
        self.processed: list[str] = []

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "backend": "stub",
            "model_loaded": True,
            "device": "cpu",
        }

    async def process_upload(self, path: str, request: Any) -> dict[str, Any]:
        self.processed.append(str(path))
        return {
            "markdown": "",
            "pages_processed": 1,
            "processing_time_seconds": 0.0,
            "backend": "stub",
            "model_info": "stub",
        }


@pytest.fixture
def service() -> _StubService:
    return _StubService()


@pytest.fixture
def client(service: _StubService, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv(API_KEY_ENV, TEST_KEY)
    app = FastAPI()
    app.include_router(ocr_router)
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_KEY}"}


# --- authentication -------------------------------------------------------


@pytest.mark.parametrize("route", ["/api/ocr/health", "/api/ocr/process", "/api/ocr/process-path"])
def test_anonymous_request_is_rejected(client: TestClient, route: str) -> None:
    """Every OCR endpoint must reject a request presenting no credential."""
    response = client.post(route) if route != "/api/ocr/health" else client.get(route)
    assert response.status_code == 401, (
        f"{route} answered {response.status_code} without a credential; "
        "expected 401. An anonymous file-read primitive is an S0."
    )


def test_valid_credential_is_accepted(client: TestClient) -> None:
    """A correct key must not be rejected -- the gate is auth, not a blanket deny."""
    response = client.get("/api/ocr/health", headers=_auth())
    assert response.status_code == 200


def test_wrong_credential_is_rejected(client: TestClient) -> None:
    response = client.get("/api/ocr/health", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_x_api_key_header_also_works(client: TestClient) -> None:
    """Both credential headers are supported by the shared security primitive."""
    response = client.get("/api/ocr/health", headers={"X-API-Key": TEST_KEY})
    assert response.status_code == 200


def test_auth_disabled_when_key_unset(
    monkeypatch: pytest.MonkeyPatch, service: _StubService
) -> None:
    """With no configured key, local development stays open (matches siblings)."""
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    app = FastAPI()
    app.include_router(ocr_router)
    app.dependency_overrides[get_service] = lambda: service
    assert TestClient(app).get("/api/ocr/health").status_code == 200


# --- path safety ----------------------------------------------------------


def test_traversal_filename_cannot_escape_temp_dir(
    client: TestClient, service: _StubService, tmp_path: Path
) -> None:
    """``../`` in the upload filename must be reduced to its basename."""
    response = client.post(
        "/api/ocr/process",
        headers=_auth(),
        files={"file": ("../../pwned.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    # The route may legitimately fail to OCR the bytes; what matters is that the
    # path handed to the service has no directory component.
    #
    # `!= 401` alone was unsatisfiable-proof: if the request never reached the
    # service, `service.processed` was empty, the loop below ran zero times, and
    # the test asserted nothing at all. Requiring the call is what makes the loop
    # meaningful (F-TEST-010).
    assert response.status_code != 401
    assert service.processed, "the request never reached the service; nothing was checked"
    for path in service.processed:
        assert ".." not in path, f"traversal reached the service: {path}"


def test_process_path_rejects_disallowed_extension(client: TestClient, tmp_path: Path) -> None:
    """An arbitrary server file must not be OCR'd and returned as text.

    ``/process-path`` previously applied no extension filter, so a caller could
    read any file the service user could read and receive its contents.
    """
    secret = tmp_path / "id_rsa"
    secret.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\n")

    response = client.post(
        "/api/ocr/process-path",
        headers=_auth(),
        data={"file_path": str(secret)},
    )
    assert response.status_code in (400, 403, 404), (
        f"/process-path accepted a disallowed extension ({response.status_code}); "
        "it would return the file's contents as OCR text."
    )
