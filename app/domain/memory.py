"""Pure Domain Entities: Memory Records & Fact Extraction.

Zero infrastructure or framework dependencies. Modern Python 3.11+ syntax.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    """Categorization of stored memories."""

    FACT = "fact"
    PREFERENCE = "preference"
    PROJECT = "project"
    ENTITY = "entity"
    INSTRUCTION = "instruction"


class MemoryKind(str, Enum):
    """Semantic kind of a memory item (Sprint 3 capability contract §2)."""

    FACT = "fact"
    EPISODE = "episode"
    PROCEDURE = "procedure"
    PREFERENCE = "preference"
    CONVERSATION = "conversation"


class MemoryScope(str, Enum):
    """Lifetime/visibility scope of a memory item (contract §2)."""

    SESSION = "session"
    USER = "user"
    GLOBAL = "global"


class DraftStatus(str, Enum):
    """Provenance/confidence marker for a memory item (contract §2)."""

    CANONICAL = "canonical"
    DRAFT = "draft"
    DEPRECATED = "deprecated"


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
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_accessed_at: datetime | None = None
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Bi-temporal validity (ADR-015). Unix timestamps to match the on-disk store.
    # `valid_at`/`invalid_at` are EVENT time (when the fact was true in the
    # world); `expired_at` is SYSTEM time (when the store stopped believing it).
    # `occurs_at` is the instant of an event, as opposed to a span.
    valid_at: float | None = None
    invalid_at: float | None = None
    expired_at: float | None = None
    occurs_at: float | None = None


@dataclass
class MemoryItem:
    """Contract-compliant memory item (docs/CAPABILITY-CONTRACT.md §2).

    The full schema the capability tracker requires for the memory subsystem:
    a concrete ``kind`` (fact/episode/procedure/preference/conversation), a
    ``scope`` (session/user/global), and provenance fields (source, confidence,
    ``draft_status``, ``lhs_entity_ids``) so every memory can be traced back to
    where it came from and how much it should be trusted.

    This is deliberately a *pure* domain type: no I/O, no framework imports, no
    side effects. Persistence and retrieval live in ``app.memory``.
    """

    id: str
    content: str
    kind: MemoryKind = MemoryKind.FACT
    scope: MemoryScope = MemoryScope.USER
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    embedding: list[float] | None = None
    keywords: list[str] = field(default_factory=list)
    source: str = "user"  # user / stemma / web / tool / inferred
    confidence: float = 1.0
    draft_status: DraftStatus = DraftStatus.CANONICAL
    lhs_entity_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, at: datetime | None = None) -> bool:
        """Whether the memory has expired (``expires_at`` passed)."""
        if self.expires_at is None:
            return False
        return (at or datetime.now(UTC)) >= self.expires_at

    def to_record(self, category: str = "general", key: str = "") -> MemoryRecord:
        """Project onto the legacy ``MemoryRecord`` shape for backends that use it."""
        return MemoryRecord(
            id=self.id,
            key=key or self.kind.value,
            value=self.content,
            category=category,
            memory_type=_kind_to_memory_type(self.kind),
            confidence=self.confidence,
            metadata=self.metadata,
            embedding=self.embedding,
        )


def _kind_to_memory_type(kind: MemoryKind) -> MemoryType:
    """Map a contract ``MemoryKind`` onto the legacy ``MemoryType`` enum."""
    mapping = {
        MemoryKind.FACT: MemoryType.FACT,
        MemoryKind.PREFERENCE: MemoryType.PREFERENCE,
        MemoryKind.PROCEDURE: MemoryType.INSTRUCTION,
        MemoryKind.EPISODE: MemoryType.PROJECT,
        MemoryKind.CONVERSATION: MemoryType.PROJECT,
    }
    return mapping.get(kind, MemoryType.FACT)


@dataclass
class FactExtractionResult:
    """Domain model representing facts extracted from conversation text."""

    facts: list[MemoryRecord] = field(default_factory=list)
    source_message_id: str | None = None
    extracted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
