"""Memory pipeline — unified extract → manage → store → retrieve flow.

Ties the Sprint 3 pieces together:

1. **Extract** — ``LLMFactExtractor`` pulls ``MemoryItem`` candidates from
   conversation text.
2. **Manage** — near-duplicate detection (``dedup``) collapses rephrased
   statements; scope filtering prunes session-scoped memories on retrieve.
3. **Store** — ``MemoryStore`` persists to the hybrid backend (Chroma +
   keyword index).
4. **Retrieve** — ``MemoryManager``'s hybrid retriever + ranker surface the
   most relevant memories for a query.

This module is the *façade* that makes the four stages callable as one.
"""

from __future__ import annotations

import logging
from typing import Any

from app.domain import MemoryItem
from app.memory.schema import SOURCE_USER

logger = logging.getLogger(__name__)


class MemoryPipeline:
    """Orchestrates the full memory flow.

    Usage::

        pipeline = MemoryPipeline(manager, extractor)
        await pipeline.extract_and_store("I prefer dark mode")
        results = pipeline.retrieve("what do I like?")
    """

    def __init__(
        self,
        manager: Any,
        extractor: Any = None,
    ) -> None:
        self._manager = manager
        self._extractor = extractor

    async def extract_and_store(
        self,
        message: str,
        source: str = SOURCE_USER,
        session_id: str | None = None,
    ) -> list[MemoryItem]:
        """Extract memories from ``message`` and store them (dedup applied).

        Returns the list of ``MemoryItem`` candidates that were actually
        stored (post-dedup).
        """
        if self._extractor is None:
            logger.debug("no extractor wired — skipping extract stage")
            return []

        candidates = self._extractor.extract(message, source=source, session_id=session_id)
        if not candidates:
            return []

        # Deduplicate against already-stored memories.
        try:
            from app.memory.dedup import deduplicate

            existing = [
                m.to_record() if hasattr(m, "to_record") else m for m in self._manager.get_all()
            ]
            # Re-hydrate as MemoryItems for dedup if needed.
            existing_items: list[MemoryItem] = []
            for e in existing:
                if isinstance(e, MemoryItem):
                    existing_items.append(e)
                elif hasattr(e, "value"):
                    from app.domain import MemoryItem as _MI

                    existing_items.append(
                        _MI(
                            id=getattr(e, "id", str(hash(e.value))),
                            content=e.value,
                        )
                    )
            unique = deduplicate(candidates + existing_items)
            # Only keep the candidates (newly extracted), not existing ones.
            new_unique = [u for u in unique if u.id in {c.id for c in candidates}]
        except Exception:  # noqa: BLE001 — dedup is best-effort
            new_unique = candidates

        # Store the deduplicated items via the manager.
        for item in new_unique:
            try:
                self._manager.store(
                    {
                        "category": "general",
                        "type": item.kind.value,
                        "value": item.content,
                        "behavior": "append",
                        "source": source,
                        "confidence": item.confidence,
                        "metadata": {
                            **item.metadata,
                            "scope": item.scope.value,
                            "draft_status": item.draft_status.value,
                            "lhs_entity_ids": item.lhs_entity_ids,
                        },
                    },
                    source=source,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to store memory item %s: %s", item.id, e)

        return new_unique

    def retrieve(self, query: str, limit: int = 20, scope_filter: str | None = None) -> list[Any]:
        """Retrieve memories, optionally filtered by scope."""
        results = self._manager.retrieve(query, limit=limit)
        if scope_filter is not None:
            results = [r for r in results if _scope_of(r) == scope_filter]
        return results


def _scope_of(result: Any) -> str | None:
    """Best-effort extraction of scope from a MemoryResult or Memory."""
    memory = getattr(result, "memory", result)
    metadata = getattr(memory, "metadata", {})
    if isinstance(metadata, dict):
        return metadata.get("scope")
    return None
