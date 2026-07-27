"""Pure Domain Entities: Memory Records & Fact Extraction.

Zero infrastructure or framework dependencies. Modern Python 3.11+ syntax.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    """Categorization of stored memories."""
    FACT = "fact"
    PREFERENCE = "preference"
    PROJECT = "project"
    ENTITY = "entity"
    INSTRUCTION = "instruction"


@dataclass
class MemoryRecord:
    """Single persistent memory record."""
    id: str
    key: str
    value: str
    category: str = "general"
    memory_type: MemoryType = MemoryType.FACT
    confidence: float = 1.0
    access_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime | None = None
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FactExtractionResult:
    """Domain model representing facts extracted from conversation text."""
    facts: list[MemoryRecord] = field(default_factory=list)
    source_message_id: str | None = None
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
