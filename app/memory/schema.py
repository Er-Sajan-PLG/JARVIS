"""
Memory schema definitions for JARVIS v2.0

Uses immutable created_at + mutable updated_at pattern.
"""

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Memory:
    """
    A single memory with rich metadata.

    Timestamps — two clocks (ADR-015):
    - created_at: When the store learned this (system time, immutable)
    - updated_at: When this memory was last modified (mutable)
    - last_used: When this memory was last retrieved (for ranking)

    Bi-temporal validity (ADR-015), all optional:
    - valid_at / invalid_at: event time — when the fact was true in the world
    - expired_at: system time — when the store stopped believing it
    - occurs_at: the instant an EVENT happens (a meeting), not a span
    - superseded_by / supersedes: the correction chain, so nothing is deleted
    """

    category: str  # e.g., "identity", "preference", "skill"
    memory_type: str  # e.g., "name", "like", "fact"
    value: str  # The actual content
    behavior: str = "append"  # "append", "replace", "ignore", "delete"

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Timestamps
    created_at: float = field(default_factory=time.time)  # Immutable: when created
    updated_at: float = field(default_factory=time.time)  # Mutable: when last modified
    last_used: float = field(default_factory=time.time)  # Mutable: when last retrieved

    # Bi-temporal validity (ADR-015). None means "open".
    valid_at: float | None = None  # event time: became true
    invalid_at: float | None = None  # event time: stopped being true
    expired_at: float | None = None  # system time: we stopped believing it
    occurs_at: float | None = None  # the instant an event happens
    superseded_by: str | None = None  # id of the fact that replaced this
    supersedes: str | None = None  # id of the fact this replaced

    # Metadata
    source: str = "user"  # "user", "system", "inferred"
    confidence: float = 1.0  # 0.0 to 1.0
    importance: float = 0.5  # 0.0 to 1.0
    access_count: int = 0

    # Additional data
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage.

        NOTE: every field added to the dataclass must be listed here. A field
        present in memory but absent from this method is silently dropped on the
        next save — which is how the temporal fields would have been lost.
        """
        return {
            "id": self.id,
            "category": self.category,
            "type": self.memory_type,
            "value": self.value,
            "behavior": self.behavior,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_used": self.last_used,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at,
            "occurs_at": self.occurs_at,
            "superseded_by": self.superseded_by,
            "supersedes": self.supersedes,
            "source": self.source,
            "confidence": self.confidence,
            "importance": self.importance,
            "access_count": self.access_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Memory":
        """Deserialize from dictionary with version handling"""
        # Handle v1 format that had single "timestamp"
        created = data.get("created_at", data.get("timestamp", time.time()))
        updated = data.get("updated_at", data.get("timestamp", time.time()))
        last_used = data.get("last_used", updated)

        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            category=data["category"],
            memory_type=data["type"],
            value=data["value"],
            behavior=data.get("behavior", "append"),
            created_at=created,
            updated_at=updated,
            last_used=last_used,
            valid_at=data.get("valid_at"),
            invalid_at=data.get("invalid_at"),
            expired_at=data.get("expired_at"),
            occurs_at=data.get("occurs_at"),
            superseded_by=data.get("superseded_by"),
            supersedes=data.get("supersedes"),
            source=data.get("source", "user"),
            confidence=data.get("confidence", 1.0),
            importance=data.get("importance", 0.5),
            access_count=data.get("access_count", 0),
            metadata=data.get("metadata", {}),
        )

    def touch(self) -> None:
        """Update last_used and increment access_count (called on retrieval)"""
        self.last_used = time.time()
        self.access_count += 1

    def mark_updated(self) -> None:
        """Mark this memory as modified (called on updates)"""
        self.updated_at = time.time()

    def format_for_prompt(self) -> str:
        """Format this memory for inclusion in a prompt"""
        return f"- [{self.category}] {self.memory_type}: {self.value}"


@dataclass
class MemoryResult:
    """
    A retrieved memory with its relevance score.
    Separated from retrieval logic - ranking produces these.
    """

    memory: Memory
    score: float = 0.0


# Constants
BEHAVIOR_APPEND = "append"
BEHAVIOR_REPLACE = "replace"
BEHAVIOR_IGNORE = "ignore"
BEHAVIOR_DELETE = "delete"

SOURCE_USER = "user"
SOURCE_SYSTEM = "system"
SOURCE_INFERRED = "inferred"

IMPORTANCE_LOW = 0.3
IMPORTANCE_MEDIUM = 0.5
IMPORTANCE_HIGH = 0.7
IMPORTANCE_CRITICAL = 0.9
