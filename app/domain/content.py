"""Pure Domain Entities: Content Abstractions & Artifact Handles.

Zero infrastructure or framework dependencies. Modern Python 3.11+ syntax.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ContentType(str, Enum):
    """Enumeration of content source types."""

    TEXT = "text"
    CODE = "code"
    FILE = "file"
    PDF = "pdf"
    IMAGE = "image"
    URL = "url"
    REPOSITORY = "repository"


@dataclass
class DocumentReference:
    """Reference to a specific location within a document or file."""

    uri: str
    title: str | None = None
    page_number: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    snippet: str | None = None


@dataclass
class ContentSource:
    """Generic abstraction for all external content consumed by the LLM & ContextBuilder."""

    source_id: str
    content_type: ContentType
    uri: str
    title: str
    raw_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    references: list[DocumentReference] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def token_estimate(self) -> int:
        """Rough token estimate based on word/character heuristic (~4 chars/token)."""
        return max(1, len(self.raw_text) // 4)


@dataclass
class ArtifactHandle(ContentSource):
    """Concrete ContentSource for disk-spilled large files (PDFs, images, binary payloads)."""

    file_path: str = ""
    mime_type: str = "application/octet-stream"
    byte_size: int = 0
    spilled_to_disk: bool = True
    ocr_extracted: bool = False
