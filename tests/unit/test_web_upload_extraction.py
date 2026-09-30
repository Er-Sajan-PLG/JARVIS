"""The web upload path must actually extract text from an uploaded file.

`POST /api/upload` returns an `extracted_text` field, and the console renders it
into the conversation. It was filled by `_read_extracted`, which reads only an
*embedded* text layer: for an image, and for a scanned PDF, it returned "" and
the caller substituted a placeholder string --

    f"[Image: {safe_name} — no text layer]"

-- so the one thing the feature exists to do, turn an uploaded file into text,
never happened for exactly the file types that need OCR. A 16 KB PNG with the
words "UPLOAD EXTRACTION PROOF" in it came back as the placeholder.

These tests drive the real route, the real service and the real engine. No
stubs: a stubbed OCR backend is what let the subsystem stay green while no
request could succeed.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.security import API_KEY_ENV
from app.adapters.web.router import web_router

TEST_KEY = "upload-extract-test-key"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    """Route wired to a temp upload dir so the test cannot touch real uploads."""
    from app.adapters.web import router as web_router_module

    monkeypatch.setenv(API_KEY_ENV, TEST_KEY)
    monkeypatch.setattr(web_router_module, "UPLOAD_DIR", tmp_path / "uploads")
    app = FastAPI()
    app.include_router(web_router)
    return TestClient(app)


def _auth() -> dict[str, str]:
    return {"X-API-Key": TEST_KEY}


@pytest.fixture
def png_with_text(tmp_path):
    """A real PNG containing known words, rendered with pymupdf."""
    import pymupdf

    out = tmp_path / "proof.png"
    doc = pymupdf.open()
    page = doc.new_page(width=700, height=220)
    page.insert_text((30, 120), "UPLOAD EXTRACTION PROOF", fontsize=30)
    page.get_pixmap(dpi=200).save(str(out))
    doc.close()
    return out


@pytest.fixture
def scanned_pdf(tmp_path):
    """A PDF whose only content is an image -- no text layer at all."""
    import pymupdf

    out = tmp_path / "scanned.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=700, height=220)
    page.insert_text((30, 120), "SCANNED PAGE PROOF", fontsize=30)
    png = tmp_path / "_page.png"
    page.get_pixmap(dpi=200).save(str(png))

    image_only = pymupdf.open()
    p2 = image_only.new_page(width=700, height=220)
    p2.insert_image(pymupdf.Rect(0, 0, 700, 220), filename=str(png))
    image_only.save(str(out))
    image_only.close()
    doc.close()
    return out


def test_upload_extracts_text_from_an_image(client: TestClient, png_with_text) -> None:
    """THE regression: an uploaded image must come back as its text.

    This returned "[Image: proof.png — no text layer]" -- a placeholder that
    reads like a successful extraction of nothing.
    """
    with open(png_with_text, "rb") as f:
        response = client.post(
            "/api/upload", headers=_auth(), files={"file": ("proof.png", f.read(), "image/png")}
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "image"
    extracted = " ".join(body["extracted_text"].split()).upper()
    assert (
        "UPLOAD EXTRACTION PROOF" in extracted
    ), f"the image was not OCR'd; got {body['extracted_text']!r}"
    assert (
        "no text layer" not in body["extracted_text"].lower()
    ), "the placeholder is still being returned instead of real text"


def test_upload_extracts_text_from_a_scanned_pdf(client: TestClient, scanned_pdf) -> None:
    """A PDF with no text layer must be OCR'd, not reported as empty."""
    with open(scanned_pdf, "rb") as f:
        response = client.post(
            "/api/upload",
            headers=_auth(),
            files={"file": ("scanned.pdf", f.read(), "application/pdf")},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (
        "SCANNED PAGE PROOF" in " ".join(body["extracted_text"].split()).upper()
    ), f"a scanned PDF was not OCR'd; got {body['extracted_text']!r}"


def test_upload_still_reads_a_plain_text_file(client: TestClient) -> None:
    """Text files must not be sent through OCR -- they are already text.

    This is the path that always worked, and OCR-ing it would be both slower
    and lossy.
    """
    payload = b"line one\nline two\n"
    response = client.post(
        "/api/upload", headers=_auth(), files={"file": ("notes.txt", payload, "text/plain")}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "text"
    assert body["extracted_text"] == "line one\nline two\n"


def test_upload_extracts_a_digital_pdf_without_ocr(client: TestClient, tmp_path) -> None:
    """A PDF with a real text layer must come back intact."""
    import pymupdf

    out = tmp_path / "digital.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "DIGITAL TEXT LAYER WORKS", fontsize=18)
    doc.save(str(out))
    doc.close()

    with open(out, "rb") as f:
        response = client.post(
            "/api/upload",
            headers=_auth(),
            files={"file": ("digital.pdf", f.read(), "application/pdf")},
        )
    assert response.status_code == 200, response.text
    assert "DIGITAL TEXT LAYER WORKS" in response.json()["extracted_text"]


def test_upload_of_an_unreadable_image_is_honest_not_a_placeholder(
    client: TestClient,
) -> None:
    """An image that genuinely yields nothing must say so, not claim a text layer.

    The old message was "[Image: x.png — no text layer]", which is a statement
    about the PDF concept of a text layer being applied to a PNG. It read as a
    successful empty extraction.
    """
    response = client.post(
        "/api/upload",
        headers=_auth(),
        files={"file": ("blank.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")},
    )
    assert response.status_code == 200, response.text
    text = response.json()["extracted_text"]
    assert "no text layer" not in text.lower(), f"the image placeholder is back: {text!r}"
