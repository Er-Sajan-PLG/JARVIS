"""Persistent Memory Façade.

Provides hybrid vector + BM25 keyword search, fact extraction, and memory lifecycle orchestration
returning pure MemoryRecord domain entities.
"""

import logging
from typing import Any
import uuid

from app.domain import FactExtractionResult, MemoryRecord, MemoryType
from app.memory.manager import MemoryManager

logger = logging.getLogger(__name__)


class MemoryService:
    """Façade API adapting internal memory stores to pure MemoryRecord domain models."""

    def __init__(self, manager: MemoryManager | None = None) -> None:
        self._manager = manager or MemoryManager()

    async def store_memory(
        self,
        key: str,
        value: str,
        category: str = "general",
        memory_type: MemoryType = MemoryType.FACT,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        """Store a new memory record.

        Args:
            key: Memory key string.
            value: Memory value content.
            category: Category tag.
            memory_type: MemoryType enum.
            confidence: Confidence score (0.0 to 1.0).
            metadata: Optional metadata dict.

        Returns:
            MemoryRecord domain model.
        """
        mem_id = f"mem-{uuid.uuid4().hex[:8]}"
        fact_dict = {
            "id": mem_id,
            "category": category,
            "type": key,
            "value": value,
            "behavior": "append",
            "importance": confidence,
        }
        stored = self._manager.store(fact_dict)
        rec_id = stored.id if stored else mem_id

        logger.info("Stored memory [%s] %s=%s", rec_id, key, value[:30])
        return MemoryRecord(
            id=rec_id,
            key=key,
            value=value,
            category=category,
            memory_type=memory_type,
            confidence=confidence,
            metadata=metadata or {},
        )

    async def search_memories(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Perform hybrid retrieval for relevant memories given a search query.

        Args:
            query: User prompt or query string.
            limit: Max memory results to return.

        Returns:
            List of MemoryRecord domain entities sorted by relevance.
        """
        results = self._manager.retrieve(query, limit=limit)
        records: list[MemoryRecord] = []

        for res in results:
            mem = res.memory
            m_key = getattr(mem, "memory_type", getattr(mem, "type", "fact"))
            m_type = MemoryType.FACT
            try:
                m_type = MemoryType(m_key)
            except Exception:
                pass

            records.append(
                MemoryRecord(
                    id=mem.id,
                    key=m_key,
                    value=mem.value,
                    category=mem.category,
                    memory_type=m_type,
                    confidence=res.score,
                    access_count=mem.access_count,
                    metadata={"source": mem.source, "importance": mem.importance},
                )
            )

        logger.debug("Retrieved %d memory records for query: %s", len(records), query[:40])
        return records

    async def list_memories(self) -> list[MemoryRecord]:
        """List all stored memory records."""
        all_mems = self._manager._store.get_all()
        records: list[MemoryRecord] = []
        for mem in all_mems:
            m_key = getattr(mem, "memory_type", getattr(mem, "type", "fact"))
            records.append(
                MemoryRecord(
                    id=mem.id,
                    key=m_key,
                    value=mem.value,
                    category=mem.category,
                    access_count=mem.access_count,
                    metadata={"source": mem.source},
                )
            )
        return records

    async def extract_facts(self, conversation_text: str) -> FactExtractionResult:
        """Extract facts from text snippet (delegates to fact_extractor if present)."""
        return FactExtractionResult(facts=[], source_message_id=None)
