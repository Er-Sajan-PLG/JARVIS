"""
Memory Store for JARVIS v2.0

Low-level CRUD and persistence. No business logic, no retrieval.
Extracted from MemoryManager to keep concerns separated.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional, get_type_hints

from app.config.settings import get_settings, MemoryConfig
from app.memory.schema import Memory, SOURCE_USER, IMPORTANCE_MEDIUM
from app.utils.corruption import backup_corrupt_file, report_corruption

logger = logging.getLogger(__name__)

# Resolved type hints for Memory, used to validate update_fields().
_TYPE_HINTS = get_type_hints(Memory)

# Fields that identify a memory or record its creation time. These must never
# be mutated after creation: changing `id` would orphan the memory in the
# vector store and break retrieval/delete by ID.
_IMMUTABLE_FIELDS = {"id", "created_at"}


def _validate_field_value(key: str, value):
    """Validate and coerce a value destined for a Memory field.

    Raises ValueError if the field is unknown, immutable, or the value cannot
    be safely stored (wrong type, out-of-range, etc.). This blocks callers —
    including a confused model — from setting ``id=None`` or
    ``confidence="banana"``.
    """
    if key not in _TYPE_HINTS:
        raise ValueError(f"unknown field {key!r}")
    if key in _IMMUTABLE_FIELDS:
        raise ValueError(f"field {key!r} is immutable and cannot be updated")

    expected = _TYPE_HINTS[key]

    if expected is float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"field {key!r} must be a number, got {value!r}")
        if key in ("confidence", "importance") and not (0.0 <= value <= 1.0):
            raise ValueError(f"field {key!r} must be between 0.0 and 1.0")
    elif expected is int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"field {key!r} must be an integer, got {value!r}")
        if key == "access_count" and value < 0:
            raise ValueError(f"field {key!r} must be >= 0")
    elif expected is str:
        if value is None:
            raise ValueError(f"field {key!r} must not be None")
        value = str(value)
    elif expected is dict:
        if not isinstance(value, dict):
            raise ValueError(f"field {key!r} must be a dict")
    return value


class MemoryStore:
    """
    Low-level storage for memories.
    
    Responsibilities:
    - CRUD operations
    - Persistence (save/load)
    - Dirty tracking
    
    NOT responsible for:
    - Retrieval (that's CandidateRetriever)
    - Ranking (that's MemoryRanker)
    - Behavior logic (that's MemoryManager)
    """
    
    def __init__(self, path: Path = None, config: MemoryConfig = None):
        settings = get_settings()
        
        self.path: Path = Path(path) if path is not None else settings.paths.memories
        self.config: MemoryConfig = config or settings.memory
        
        self._memories: list[Memory] = []
        self._dirty: bool = False
        
        self._load()
    
    # ===== CRUD Operations =====
    
    def add(self, memory: Memory) -> Memory:
        """Add a new memory to the store"""
        self._memories.append(memory)
        self._dirty = True
        return memory
    
    def get_by_id(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID"""
        for m in self._memories:
            if m.id == memory_id:
                return m
        return None
    
    def find_by_category_and_type(self, category: str, memory_type: str) -> list[Memory]:
        """Find all memories matching category and type"""
        return [
            m for m in self._memories 
            if m.category == category and m.memory_type == memory_type
        ]
    
    def get_all(self) -> list[Memory]:
        """Get all memories"""
        return list(self._memories)
    
    def update_fields(self, memory_id: str, updates: dict) -> Optional[Memory]:
        """
        Update specific fields on a memory, with type validation.

        Does NOT handle behavior logic - that's MemoryManager's job.
        Unknown fields and values that fail validation are skipped (with a
        warning) rather than stored, so a bad/attacker-supplied update can
        never corrupt a memory's type invariants.
        """
        memory = self.get_by_id(memory_id)
        if not memory:
            return None
        
        for key, value in updates.items():
            try:
                validated = _validate_field_value(key, value)
            except ValueError as exc:
                logger.warning(
                    "Skipping invalid update to memory %s field %r: %s",
                    memory_id, key, exc,
                )
                continue
            setattr(memory, key, validated)

        memory.mark_updated()
        self._dirty = True
        return memory
    
    def remove(self, memory_id: str) -> Optional[Memory]:
        """Remove a memory by ID, returns the removed memory or None"""
        for i, m in enumerate(self._memories):
            if m.id == memory_id:
                removed = self._memories.pop(i)
                self._dirty = True
                return removed
        return None
    
    def remove_by_category_and_type(self, category: str, memory_type: str) -> list[Memory]:
        """Remove all memories matching category and type"""
        to_remove = self.find_by_category_and_type(category, memory_type)
        
        for m in to_remove:
            self._memories.remove(m)
        
        if to_remove:
            self._dirty = True
        
        return to_remove
    
    def count(self) -> int:
        """Return total number of memories"""
        return len(self._memories)
    
    def clear(self) -> None:
        """Remove all memories"""
        self._memories.clear()
        self._dirty = True
        self.save()
    
    # ===== Persistence =====
    
    @property
    def is_dirty(self) -> bool:
        """Check if there are unsaved changes"""
        return self._dirty
    
    def save(self) -> None:
        """Save all memories to disk (atomically and durably)."""
        if not self._dirty:
            return
        
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "version": "2.0",
            "memories": [m.to_dict() for m in self._memories]
        }
        
        # Atomic, durable write: serialize to a temp file in the same directory,
        # flush + fsync, then os.replace() (atomic rename) over the target.
        # This prevents a partially-written / truncated file from corrupting the
        # on-disk state if the process is interrupted mid-write.
        tmp_path = self.path.with_name(f"{self.path.name}.tmp.{os.getpid()}")
        try:
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.path)
            self._dirty = False
        except BaseException:
            # Best-effort cleanup of the temp file so we don't litter the data dir.
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            raise
    
    def save_if_dirty(self) -> None:
        """Public method to save only if changes were made"""
        self.save()
    
    def force_save(self) -> None:
        """Force save regardless of dirty state"""
        self._dirty = True
        self.save()
    
    def _load(self) -> None:
        """
        Load memories from disk, handling v1 and v2 formats.

        Robustness: deserialization failures are caught and reported the same
        way as parse failures (the corrupt file is quarantined to a backup so
        its bytes survive the next save). A single malformed *record* no longer
        wipes every memory - it is skipped with a warning instead.
        """
        self._memories = []
        self._dirty = False

        if not self.path.exists():
            return
        
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            # Corruption / unreadable file: do NOT silently start empty.
            # Quarantine the bad file so the next save() can't destroy it,
            # then warn loudly.
            backup = backup_corrupt_file(self.path)
            report_corruption(logger, "memories", self.path, exc, backup)
            return

        memories, had_bad_records = self._deserialize(data)
        self._memories = memories

        # If we dropped malformed records, rewrite the file clean on the next
        # save so it no longer carries corrupt entries.
        if had_bad_records:
            self._dirty = True

    def _deserialize(self, data) -> tuple[list[Memory], bool]:
        """
        Convert parsed JSON into Memory objects.

        Returns (memories, had_bad_records). Malformed individual records are
        skipped (not fatal) so one bad entry can't discard the whole store.
        """
        if isinstance(data, dict) and "version" in data:
            raw = data.get("memories", [])
        elif isinstance(data, dict) and "facts" in data:
            raw = data["facts"]
        elif isinstance(data, list):
            # A bare list at the memories path is unexpected (no memory records).
            # Warn, but there is nothing to lose by starting empty.
            logger.warning(
                "Memories file %s contained a bare list; treating as empty.",
                self.path,
            )
            return [], False
        else:
            logger.warning(
                "Unrecognized memories file structure in %s; treating as empty.",
                self.path,
            )
            return [], False

        memories: list[Memory] = []
        bad = 0
        for record in raw:
            if not isinstance(record, dict):
                bad += 1
                continue
            try:
                memories.append(Memory.from_dict(record))
            except (KeyError, TypeError, ValueError) as exc:
                bad += 1
                logger.warning(
                    "Skipping malformed memory record in %s: %s", self.path, exc
                )

        if bad:
            logger.warning(
                "Dropped %d malformed memory record(s) from %s.", bad, self.path
            )

        return memories, bad > 0

