"""Unit tests for app/artifacts/manager.py (ArtifactManager)."""

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from app.artifacts.manager import ArtifactManager
from app.domain import ArtifactHandle, ContentType


def test_artifact_manager_init(tmp_path: Path) -> None:
    storage = tmp_path / "artifacts_store"
    ArtifactManager(storage_dir=storage)
    assert storage.is_dir()


def test_spill_bytes_code_file(tmp_path: Path) -> None:
    mgr = ArtifactManager(storage_dir=tmp_path)
    code_content = b"print('Hello world!')\n" * 10

    handle = mgr.spill_bytes(
        content_bytes=code_content,
        filename="test_script.py",
        mime_type="text/x-python",
        metadata={"author": "test"},
    )

    assert isinstance(handle, ArtifactHandle)
    assert handle.content_type == ContentType.CODE
    assert handle.title == "test_script.py"
    assert handle.byte_size == len(code_content)
    assert handle.spilled_to_disk is True
    assert handle.metadata == {"author": "test"}
    assert "print('Hello world!')" in handle.raw_text
    assert Path(handle.file_path).exists()


def test_spill_bytes_pdf_and_image(tmp_path: Path) -> None:
    mgr = ArtifactManager(storage_dir=tmp_path)

    # PDF detection
    pdf_handle = mgr.spill_bytes(
        content_bytes=b"%PDF-1.4 dummy",
        filename="doc.pdf",
        mime_type="application/pdf",
    )
    assert pdf_handle.content_type == ContentType.PDF
    assert pdf_handle.raw_text == ""  # No raw text preview for PDF

    # Image detection
    img_handle = mgr.spill_bytes(
        content_bytes=b"\x89PNG dummy",
        filename="image.png",
        mime_type="image/png",
    )
    assert img_handle.content_type == ContentType.IMAGE
    assert img_handle.raw_text == ""

    # Generic file
    generic_handle = mgr.spill_bytes(
        content_bytes=b"\x00\x01\x02",
        filename="binary.bin",
        mime_type="application/octet-stream",
    )
    assert generic_handle.content_type == ContentType.FILE


def test_spill_bytes_deduplication(tmp_path: Path) -> None:
    mgr = ArtifactManager(storage_dir=tmp_path)
    data = b"identical content"

    h1 = mgr.spill_bytes(data, "file.txt")
    h2 = mgr.spill_bytes(data, "file.txt")

    assert h1.file_path == h2.file_path
    assert h1.source_id == h2.source_id


def test_preview_truncation_and_error(tmp_path: Path) -> None:
    mgr = ArtifactManager(storage_dir=tmp_path)
    long_code = ("x = 1\n" * 500).encode("utf-8")  # > 2000 chars

    handle = mgr.spill_bytes(long_code, "long.py", mime_type="text/x-python")
    assert len(handle.raw_text) == 2000

    # Error reading file during preview
    with patch.object(Path, "read_text", side_effect=OSError("Read error")):
        preview = mgr._extract_preview(Path(handle.file_path), ContentType.CODE)
        assert preview == ""


def test_spill_stream_and_get_artifact_bytes(tmp_path: Path) -> None:
    mgr = ArtifactManager(storage_dir=tmp_path)
    payload = b"streamed data content"
    stream = BytesIO(payload)

    handle = mgr.spill_stream(stream, "streamed.txt", mime_type="text/plain")
    assert handle.byte_size == len(payload)

    # Retrieve bytes
    retrieved = mgr.get_artifact_bytes(handle)
    assert retrieved == payload

    # Missing file raises FileNotFoundError
    handle.file_path = "/non/existent/path/artifact.bin"
    with pytest.raises(FileNotFoundError):
        mgr.get_artifact_bytes(handle)
