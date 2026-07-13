"""
Memory schema definitions for JARVIS v2.0

Uses immutable created_at + mutable updated_at pattern.
"""

from dataclasses import dataclass, field
import uuid
import time


@dataclass
class Memory:
    """
    A single memory with rich metadata.
    
    Timestamps:
    - created_at: When this memory was first created (immutable)
    - updated_at: When this memory was last modified (mutable)
    - last_used: When this memory was last retrieved (for ranking)
    """
    category: str                          # e.g., "identity", "preference", "skill"
    memory_type: str                       # e.g., "name", "like", "fact"
    value: str                             # The actual content
    behavior: str = "append"               # "append", "replace", "ignore", "delete"
    
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    # Timestamps
    created_at: float = field(default_factory=time.time)  # Immutable: when created
    updated_at: float = field(default_factory=time.time)  # Mutable: when last modified
    last_used: float = field(default_factory=time.time)   # Mutable: when last retrieved
    
    # Metadata
    source: str = "user"                   # "user", "system", "inferred"
    confidence: float = 1.0                # 0.0 to 1.0
    importance: float = 0.5                # 0.0 to 1.0
    access_count: int = 0
    
    # Additional data
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage"""
        return {
            "id": self.id,
            "category": self.category,
            "type": self.memory_type,
            "value": self.value,
            "behavior": self.behavior,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_used": self.last_used,
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
