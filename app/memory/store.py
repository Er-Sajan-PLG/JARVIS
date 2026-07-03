"""
Memory Store for JARVIS v2.0

Low-level CRUD and persistence. No business logic, no retrieval.
Extracted from MemoryManager to keep concerns separated.
"""

import json
from pathlib import Path
from typing import Optional

from app.config.settings import get_settings, MemoryConfig
from app.memory.schema import Memory, SOURCE_USER, IMPORTANCE_MEDIUM


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
        
        self.path: Path = path or settings.paths.memories
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
        Update specific fields on a memory.
        Does NOT handle behavior logic - that's MemoryManager's job.
        """
        memory = self.get_by_id(memory_id)
        if not memory:
            return None
        
        for key, value in updates.items():
            if hasattr(memory, key):
                setattr(memory, key, value)
        
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
        """Save all memories to disk"""
        if not self._dirty:
            return
        
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "version": "2.0",
            "memories": [m.to_dict() for m in self._memories]
        }
        
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)
        
        self._dirty = False
    
    def save_if_dirty(self) -> None:
        """Public method to save only if changes were made"""
        self.save()
    
    def force_save(self) -> None:
        """Force save regardless of dirty state"""
        self._dirty = True
        self.save()
    
    def _load(self) -> None:
        """Load memories from disk, handling v1 and v2 formats"""
        if not self.path.exists():
            return
        
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return
        
        # V2 format
        if isinstance(data, dict) and "version" in data:
            self._memories = [Memory.from_dict(m) for m in data.get("memories", [])]
        
        # V1 format (dict with facts list)
        elif isinstance(data, dict) and "facts" in data:
            self._memories = [Memory.from_dict(f) for f in data["facts"]]
        
        # V1 format (just a list - conversation only, no facts)
        elif isinstance(data, list):
            self._memories = []
        
        self._dirty = False