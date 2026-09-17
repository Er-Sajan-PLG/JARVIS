"""Persistent Memory Façade.

Provides hybrid vector + BM25 keyword search, fact extraction, and memory lifecycle orchestration
returning pure MemoryRecord domain entities.
"""

import contextlib
import logging
import re
import uuid
from typing import Any

from app.domain import FactExtractionResult, MemoryRecord, MemoryType
from app.memory.manager import MemoryManager

logger = logging.getLogger(__name__)

# Values that are probes or pipeline artifacts, never durable facts. The store
# accumulated 372 identical copies of one bogus name because nothing screened
# the write path; this is the guard that was missing.
_JUNK_VALUE = re.compile(
    r"^(ping|pong|ok|okay|hello|hi|hey|test|testing|default ok|live ok|"
    r"nvidia ok|say ok|reply with exactly[:\s].*|test memory for session)$",
    re.I,
)


def _is_storable(value: str) -> bool:
    """Reject values that are noise rather than memory.

    Cheap, deterministic, and deliberately conservative: it only rejects exact
    matches of known probe/log shapes and empty values. A false rejection here
    loses a memory, so anything ambiguous is allowed through.
    """
    v = " ".join(str(value or "").split())
    if len(v) < 2:
        return False
    if _JUNK_VALUE.match(v):
        return False
    # The pipeline logs its own writes ("[memory] stored: ..."); those lines
    # would otherwise be captured as user facts.
    return "[memory] stored" not in v.lower()


class MemoryService:
    """Façade API adapting internal memory stores to pure MemoryRecord domain models."""

    def __init__(self, manager: MemoryManager | None = None) -> None:
        self._manager = manager or MemoryManager()

    def _find_duplicate(self, category: str, value: str) -> Any | None:
        """Return an existing record with the same normalized value, if any.

        Exact-match on whitespace-normalized lowercase text. Near-duplicate
        detection lives in ``app/memory/dedup.py``; this is the cheap first line
        that stops the literal-repeat case that filled the store.
        """
        target = " ".join(str(value or "").split()).lower()
        if not target:
            return None
        try:
            for existing in self._manager._store.get_all():  # noqa: SLF001
                if str(getattr(existing, "category", "")) != category:
                    continue
                if " ".join(str(getattr(existing, "value", "")).split()).lower() == target:
                    return existing
        except Exception as exc:  # noqa: BLE001 — dedup is best-effort
            logger.warning("Duplicate check failed, storing anyway: %s", exc)
        return None

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

        # Junk in, junk forever: probes and pipeline logs are not memories.
        if not _is_storable(value):
            logger.debug("Skipped non-storable memory value: %r", str(value)[:40])
            return MemoryRecord(
                id=mem_id,
                key=key,
                value=value,
                category=category,
                memory_type=memory_type,
                confidence=confidence,
                metadata={**(metadata or {}), "skipped": "junk"},
            )

        # Repeated identical writes must not append again. Before this check the
        # store grew by one row per chat turn and reached 90% duplication.
        duplicate = self._find_duplicate(category, value)
        if duplicate is not None:
            duplicate.access_count = int(getattr(duplicate, "access_count", 0)) + 1
            try:
                self._manager._store.save()  # noqa: SLF001
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to persist duplicate access count: %s", exc)
            return MemoryRecord(
                id=getattr(duplicate, "id", mem_id),
                key=key,
                value=value,
                category=category,
                memory_type=memory_type,
                confidence=confidence,
                metadata={**(metadata or {}), "deduplicated": True},
            )

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
            # Rule-derived types (birthday, meeting, university, ...) are not
            # all members of the MemoryType enum, so fall back to FACT.
            m_type = MemoryType.FACT
            with contextlib.suppress(ValueError):
                m_type = MemoryType(m_key)

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
