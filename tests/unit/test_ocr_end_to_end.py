"""End-to-end OCR tests: the real route, the real service, the real engine.

No stubs, no mocks, no patched collaborators. Every other OCR test in this
suite replaces something at the seam that was broken -- which is precisely why
the subsystem stayed green for two months while no request could succeed:

* ``test_ocr_backends.py`` used to create the missing ``settings.ocr`` attribute
  itself before asserting ``get_info()`` worked;
* ``test_ocr_model_manager.py`` patched both backend classes, so its one real
  ``get_status()`` call only ever saw ``MagicMock`` objects;
* ``test_ocr_routes_auth.py`` uses a ``_StubService`` whose ``health_check``
  returns a hardcoded ``"healthy"``.

These tests would each have failed on the broken code, and they fail now if the
engine is unavailable, because they assert on **text extracted from a file**.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.security import API_KEY_ENV
from app.api.ocr.routes import ocr_router

TEST_KEY = "ocr-e2e-test-key"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv(API_KEY_ENV, TEST_KEY)
    app = FastAPI()
    app.include_router(ocr_router)
    return TestClient(app)


def _auth() -> dict[str, str]:
    return {"X-API-Key": TEST_KEY}


@pytest.fixture
def png_with_text(tmp_path):
    """A real PNG containing known text, made with pymupdf (a real dependency)."""
    import pymupdf

    out = tmp_path / "proof.png"
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=200)
    page.insert_text((40, 110), "END TO END PROOF 24680", fontsize=26)
    page.get_pixmap(dpi=200).save(str(out))
    doc.close()
    return out


@pytest.fixture
def digital_pdf(tmp_path):
    """A PDF with a real embedded text layer -- no OCR should be needed."""
    import pymupdf

    out = tmp_path / "native.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "NATIVE PDF TEXT LAYER", fontsize=18)
    doc.save(str(out))
    doc.close()
    return out


def test_health_reports_a_real_engine(client: TestClient) -> None:
    """Health must describe the engine that will actually serve requests.

    The old endpoint answered ``{"status": "loading", "backend": null}`` on a
    cold start and then 500 forever after the first attempt.
    """
    response = client.get("/api/ocr/health", headers=_auth())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"healthy", "degraded"}
    if body["status"] == "degraded":
        pytest.fail(f"OCR engine is not usable on this host: {body.get('error')}")
    assert body["backend"] == "tesseract"
    assert body["model_loaded"] is True
    assert body["device"] == "cpu"


def test_health_survives_a_failed_processing_attempt(
    client: TestClient, png_with_text
) -> None:
    """THE regression: one request must not poison /health permanently.

    A backend was registered *before* its ``load()`` ran, so a failed load
    stayed registered; ``get_status()`` then called ``get_info()`` on it and
    raised, and every subsequent ``/api/ocr/health`` returned HTTP 500 for the
    lifetime of the process.
    """
    with open(png_with_text, "rb") as f:
        client.post(
            "/api/ocr/process",
            headers=_auth(),
            files={"file": ("proof.png", f.read(), "image/png")},
        )
    # A malformed request too, for good measure.
    client.post(
        "/api/ocr/process",
        headers=_auth(),
        files={"file": ("bad.png", b"not an image at all", "image/png")},
    )

    response = client.get("/api/ocr/health", headers=_auth())
    assert response.status_code == 200, "health must never be poisoned by a request"
    assert response.json()["status"] == "healthy"


def test_process_extracts_text_from_an_image(client: TestClient, png_with_text) -> None:
    """The whole point of the feature: an uploaded image becomes its text."""
    with open(png_with_text, "rb") as f:
        response = client.post(
            "/api/ocr/process",
            headers=_auth(),
            files={"file": ("proof.png", f.read(), "image/png")},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "END TO END PROOF 24680" in " ".join(body["markdown"].split()).upper()
    assert body["pages_processed"] == 1
    assert body["backend"] == "tesseract"
    assert body["processing_time_seconds"] >= 0.0
    # The response must carry the timing the route's response_model requires.
    # The service used to return the backend's dataclass here, which had no
    # processing_time_seconds field at all.
    assert isinstance(body["processing_time_seconds"], float)


def test_process_uses_the_text_layer_for_a_digital_pdf(
    client: TestClient, digital_pdf
) -> None:
    """A PDF with a text layer must be read directly, with no OCR at all."""
    with open(digital_pdf, "rb") as f:
        response = client.post(
            "/api/ocr/process",
            headers=_auth(),
            files={"file": ("native.pdf", f.read(), "application/pdf")},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "NATIVE PDF TEXT LAYER" in body["markdown"]
    assert body["pages_processed"] == 1
    assert "0 ocr" in body["model_info"], (
        f"a digital PDF must not be OCR'd, got model_info={body['model_info']!r}"
    )


def test_process_rejects_a_non_document_with_a_clear_error(client: TestClient) -> None:
    """A file that is not a real image must fail as 502, not a bare 500.

    The documented contract promises 502 for a processing failure. Previously
    this returned a 500 whose body echoed internal exception text.
    """
    response = client.post(
        "/api/ocr/process",
        headers=_auth(),
        files={"file": ("fake.png", b"this is not a png", "image/png")},
    )
    assert response.status_code == 502
    # The body must name the failure without echoing the raw exception text.
    assert "Invalid image" in response.json()["detail"]


def test_path_endpoint_extracts_the_same_text(client: TestClient, png_with_text) -> None:
    """``/process-path`` must work too -- it previously had no error handling."""
    response = client.post(
        "/api/ocr/process-path",
        headers=_auth(),
        data={"file_path": str(png_with_text)},
    )
    assert response.status_code == 200, response.text
    assert "END TO END PROOF 24680" in " ".join(response.json()["markdown"].split()).upper()


def test_upload_leaves_no_temporary_directory_behind(
    client: TestClient, png_with_text
) -> None:
    """The upload temp dir must not survive the request, on any path.

    It was cleaned by a ``BackgroundTasks`` entry, which is dropped whenever the
    handler raises -- so every failure leaked the entire upload.
    """
    import glob

    before = set(glob.glob("/tmp/jarvis_ocr_*"))
    with open(png_with_text, "rb") as f:
        client.post(
            "/api/ocr/process",
            headers=_auth(),
            files={"file": ("proof.png", f.read(), "image/png")},
        )
    # And a failing request, which is the path that used to leak.
    client.post(
        "/api/ocr/process",
        headers=_auth(),
        files={"file": ("bad.png", b"nope", "image/png")},
    )
    assert set(glob.glob("/tmp/jarvis_ocr_*")) - before == set()
