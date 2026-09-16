"""
Candidate Retrieval for JARVIS v2.0

Finds candidate memories that MIGHT be relevant.
Does NOT rank or score them - that's MemoryRanker's job.
"""

from typing import Protocol

from app.memory.schema import Memory
from app.utils.text import STOP_WORDS, extract_keywords


class CandidateRetriever(Protocol):
    """Protocol for candidate retrieval."""

    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]: ...

    def on_memory_added(self, memory: Memory) -> None: ...

    def on_memory_removed(self, memory_id: str) -> None: ...

    def on_index_rebuilt(self, memories: list[Memory]) -> None: ...

    def clear(self) -> None: ...


class KeywordRetriever:
    """Keyword-based candidate retrieval."""

    def __init__(self, min_keyword_overlap: int = 1):
        self._memories: list[Memory] = []
        self._min_overlap = min_keyword_overlap

    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]:
        if not self._memories or not query:
            return []

        query_keywords = self._extract_keywords(query)
        if not query_keywords:
            return []

        # Collect every memory that meets the minimum keyword-overlap, together
        # with its overlap count. We deliberately do NOT stop at `limit` by
        # insertion order - that would arbitrarily drop more relevant memories
        # stored later. Instead we rank candidates by overlap (the stable sort
        # preserves insertion order as a tiebreak) and return the top `limit`.
        scored: list[tuple[int, Memory]] = []
        for memory in self._memories:
            memory_keywords = self._get_memory_keywords(memory)
            overlap = len(query_keywords & memory_keywords)

            if overlap >= self._min_overlap:
                scored.append((overlap, memory))

        if not scored:
            return []

        scored.sort(key=lambda item: item[0], reverse=True)

        if limit is not None and len(scored) > limit:
            scored = scored[:limit]

        return [memory for _, memory in scored]

    def on_memory_added(self, memory: Memory) -> None:
        if memory not in self._memories:
            self._memories.append(memory)

    def on_memory_removed(self, memory_id: str) -> None:
        self._memories = [m for m in self._memories if m.id != memory_id]

    def on_index_rebuilt(self, memories: list[Memory]) -> None:
        self._memories = list(memories)

    def clear(self) -> None:
        self._memories.clear()

    def _extract_keywords(self, text: str) -> set[str]:
        return extract_keywords(text, STOP_WORDS)

    def _get_memory_keywords(self, memory: Memory) -> set[str]:
        text = f"{memory.value} {memory.category} {memory.memory_type}"
        return extract_keywords(text, STOP_WORDS)
