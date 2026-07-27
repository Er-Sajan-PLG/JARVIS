"""ArtifactManager & Disk Spillover Storage.

Manages external content artifacts (PDFs, images, repositories, uploads), spilling large binary payloads
to local disk storage and returning clean ContentSource / ArtifactHandle domain models.
"""

import hashlib
import logging
from pathlib import Path
from typing import Any, BinaryIO

from app.domain import ArtifactHandle, ContentType

logger = logging.getLogger(__name__)


class ArtifactManager:
    """Manages disk spillover and retrieval of binary content artifacts."""

    def __init__(self, storage_dir: str | Path = "data/artifacts") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def spill_bytes(
        self,
        content_bytes: bytes,
        filename: str,
        mime_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactHandle:
        """Spill in-memory bytes to disk storage and return an ArtifactHandle.

        Args:
            content_bytes: Raw binary payload.
            filename: Original filename.
            mime_type: Content MIME type.
            metadata: Optional metadata dictionary.

        Returns:
            ArtifactHandle domain entity.
        """
        # Generate stable artifact ID from content hash
        content_hash = hashlib.sha256(content_bytes).hexdigest()[:16]
        ext = Path(filename).suffix
        safe_name = f"{content_hash}_{Path(filename).name}"
        dest_path = self.storage_dir / safe_name

        if not dest_path.exists():
            dest_path.write_bytes(content_bytes)
            logger.info("Spilled %d bytes to %s", len(content_bytes), dest_path)

        content_type = self._detect_content_type(mime_type, filename)
        text_preview = self._extract_preview(dest_path, content_type)

        return ArtifactHandle(
            source_id=f"art-{content_hash}",
            content_type=content_type,
            uri=f"file://{dest_path.absolute()}",
            title=filename,
            raw_text=text_preview,
            file_path=str(dest_path.absolute()),
            mime_type=mime_type,
            byte_size=len(content_bytes),
            spilled_to_disk=True,
            metadata=metadata or {},
        )

    def spill_stream(
        self,
        stream: BinaryIO,
        filename: str,
        mime_type: str = "application/octet-stream",
    ) -> ArtifactHandle:
        """Stream binary data to disk spillover storage."""
        data = stream.read()
        return self.spill_bytes(data, filename, mime_type)

    def get_artifact_bytes(self, artifact: ArtifactHandle) -> bytes:
        """Retrieve raw bytes for an artifact."""
        path = Path(artifact.file_path)
        if not path.exists():
            raise FileNotFoundError(f"Artifact file missing: {artifact.file_path}")
        return path.read_bytes()

    def _detect_content_type(self, mime_type: str, filename: str) -> ContentType:
        """Detect domain ContentType from MIME type or filename extension."""
        mime = mime_type.lower()
        name = filename.lower()
        if "pdf" in mime or name.endswith(".pdf"):
            return ContentType.PDF
        if "image" in mime or any(name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
            return ContentType.IMAGE
        if any(name.endswith(ext) for ext in (".py", ".js", ".ts", ".html", ".css", ".go", ".rs", ".c")):
            return ContentType.CODE
        return ContentType.FILE

    def _extract_preview(self, path: Path, content_type: ContentType) -> str:
        """Extract lightweight text preview from spilled file if possible."""
        try:
            if content_type in (ContentType.TEXT, ContentType.CODE):
                return path.read_text(encoding="utf-8", errors="replace")[:2000]
        except Exception as e:
            logger.warning("Could not extract preview for %s: %s", path, e)
        return ""
