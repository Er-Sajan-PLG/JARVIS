"""
Memory Manager for JARVIS v2.0

High-level orchestration layer. Delegates to:
- MemoryStore: CRUD + persistence
- CandidateRetriever: Finding candidates
- MemoryRanker: Scoring and sorting

This is the ONLY class external code should interact with.
"""

import time
from typing import Optional, Callable

from app.config.settings import get_settings, MemoryConfig
from app.memory.schema import (
    Memory, MemoryResult,
    BEHAVIOR_APPEND, BEHAVIOR_REPLACE, BEHAVIOR_IGNORE, BEHAVIOR_DELETE,
    SOURCE_USER, IMPORTANCE_MEDIUM
)
from app.memory.store import MemoryStore
from app.memory.retrieval import CandidateRetriever, KeywordRetriever
from app.memory.ranking import MemoryRanker, RankingWeights


class MemoryManager:
    """
    High-level memory orchestration.
    
    Handles:
    - Behavior logic (append/replace/ignore/delete)
    - Coordinating store + retriever + ranker
    - Callbacks for memory lifecycle events
    
    Delegates to:
    - MemoryStore for persistence
    - CandidateRetriever for finding candidates
    - MemoryRanker for scoring
    """
    
    def __init__(
        self,
        path: str = None,
        config: MemoryConfig = None,
        retriever: CandidateRetriever = None,
        ranker: MemoryRanker = None,
        ranking_weights: RankingWeights = None
    ):
        settings = get_settings()
        
        self.config = config or settings.memory
        self._store = MemoryStore(path=path, config=self.config)
        
        # Initialize retriever and rebuild index from loaded memories
        self._retriever = retriever or KeywordRetriever()
        self._retriever.on_index_rebuilt(self._store.get_all())
        
        # Initialize ranker
        self._ranker = ranker or MemoryRanker(weights=ranking_weights)
        
        # Callbacks
        self._on_store: Optional[Callable] = None
        self._on_update: Optional[Callable] = None
        self._on_delete: Optional[Callable] = None
    
    # ===== High-Level Interface =====
    
    def store(self, fact: dict, source: str = SOURCE_USER) -> Optional[Memory]:
        """
        Store a new memory, handling behavior rules.
        
        This is the main entry point for storing facts.
        Behavior logic lives here, not in the store.
        """
        behavior = fact.get("behavior", BEHAVIOR_APPEND)
        
        if behavior == BEHAVIOR_IGNORE:
            return None
        
        if behavior == BEHAVIOR_DELETE:
            self.delete_by_type(fact["category"], fact["type"])
            return None
        
        if behavior == BEHAVIOR_REPLACE:
            return self._handle_replace(fact, source)
        
        return self._handle_append(fact, source)
    
    def retrieve(self, prompt: str, limit: int = None) -> list[MemoryResult]:
        """
        Retrieve relevant memories for a prompt.
        
        Pipeline:
        1. Get candidates from retriever (overshoot)
        2. Rank candidates
        3. Update access stats on returned memories
        """
        limit = limit or self.config.retrieval_limit
        
        # Get candidates (overshoot to give ranker more to work with)
        candidate_limit = min(limit * 3, self._store.count() or 50)
        candidates = self._retriever.find_candidates(prompt, limit=candidate_limit)
        
        # Rank and trim
        results = self._ranker.rank(
            candidates=candidates,
            query=prompt,
            limit=limit,
            min_score=self.config.min_relevance_score
        )
        
        # Update access stats on used memories
        if results:
            for result in results:
                result.memory.touch()
            self._store.force_save()
        
        return results
    
    def update(self, memory_id: str, updates: dict) -> Optional[Memory]:
        """Update an existing memory's fields"""
        memory = self._store.update_fields(memory_id, updates)
        
        if memory and self._on_update:
            self._on_update(memory)
        
        self._store.save_if_dirty()
        return memory
    
    def replace(self, fact: dict, source: str = SOURCE_USER) -> Memory:
        """Replace a memory matching category+type, or append if no match"""
        return self._handle_replace(fact, source)
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID"""
        removed = self._store.remove(memory_id)
        
        if removed:
            self._retriever.on_memory_removed(memory_id)
            if self._on_delete:
                self._on_delete(removed)
            self._store.save()
            return True
        
        return False
    
    def delete_by_type(self, category: str, memory_type: str) -> int:
        """Delete all memories matching category and type"""
        removed = self._store.remove_by_category_and_type(category, memory_type)
        
        for memory in removed:
            self._retriever.on_memory_removed(memory.id)
            if self._on_delete:
                self._on_delete(memory)
        
        if removed:
            self._store.save()
        
        return len(removed)
    
    def merge(self, memory_id: str, new_data: dict) -> Optional[Memory]:
        """
        Merge new data into an existing memory.

        Works on a copy of ``new_data`` so the caller's dict is never mutated.
        """
        memory = self._store.get_by_id(memory_id)
        if memory is None:
            return self.update(memory_id, new_data)

        merged = dict(new_data)
        if "value" in merged and merged["value"] not in memory.value:
            merged["value"] = f"{memory.value}; {merged['value']}"

        return self.update(memory_id, merged)
    
    # ===== Query Methods (pass-through to store) =====
    
    def get_all(self) -> list[Memory]:
        return self._store.get_all()
    
    def get_by_category(self, category: str) -> list[Memory]:
        return [m for m in self._store.get_all() if m.category == category]
    
    def get_by_type(self, category: str, memory_type: str) -> list[Memory]:
        return self._store.find_by_category_and_type(category, memory_type)
    
    def get_by_id(self, memory_id: str) -> Optional[Memory]:
        return self._store.get_by_id(memory_id)
    
    def count(self) -> int:
        return self._store.count()
    
    @property
    def is_dirty(self) -> bool:
        """Whether the underlying store has unsaved changes."""
        return self._store.is_dirty

    def clear(self):
        self._store.clear()
        self._retriever.clear()
    
    # ===== Persistence (pass-through to store) =====
    
    def save(self):
        self._store.save()
    
    def save_if_dirty(self):
        self._store.save_if_dirty()
    
    # ===== Callbacks =====
    
    def on_store(self, callback: Callable):
        self._on_store = callback
    
    def on_update(self, callback: Callable):
        self._on_update = callback
    
    def on_delete(self, callback: Callable):
        self._on_delete = callback
    
    # ===== Internal Methods =====
    
    def _handle_append(self, fact: dict, source: str) -> Memory:
        """Handle append behavior"""
        memory = Memory(
            category=fact["category"],
            memory_type=fact["type"],
            value=fact["value"],
            behavior=fact.get("behavior", BEHAVIOR_APPEND),
            source=source,
            confidence=fact.get("confidence", 1.0),
            importance=fact.get("importance", IMPORTANCE_MEDIUM),
            metadata=dict(fact["metadata"]) if fact.get("metadata") else {},
        )
        
        self._store.add(memory)
        self._retriever.on_memory_added(memory)
        
        if self._on_store:
            self._on_store(memory)
        
        self._store.save()
        return memory
    
    def _handle_replace(self, fact: dict, source: str) -> Memory:
        """Handle replace behavior"""
        existing = self._store.find_by_category_and_type(fact["category"], fact["type"])
        
        if existing:
            # Replace first match, preserving any metadata the caller supplied.
            memory = existing[0]
            memory.value = fact["value"]
            memory.source = source
            if "confidence" in fact:
                memory.confidence = fact["confidence"]
            if "importance" in fact:
                memory.importance = fact["importance"]
            if "behavior" in fact:
                memory.behavior = fact["behavior"]
            if fact.get("metadata"):
                memory.metadata = dict(fact["metadata"])
            memory.mark_updated()
            
            if self._on_update:
                self._on_update(memory)
            
            self._store.force_save()
            return memory
        
        # No match found, append new
        return self._handle_append(fact, source)
    
    # ===== Legacy Compatibility =====
    
    @property
    def facts(self) -> list[dict]:
        """Legacy property for backward compatibility"""
        return [m.to_dict() for m in self._store.get_all()]
    
    def load(self) -> tuple[list[dict], list[dict]]:
        """Legacy load method. Returns (conversation, facts)."""
        return [], self.facts
    
    def add_fact(self, fact: dict):
        """Legacy method for backward compatibility"""
        self.store(fact)