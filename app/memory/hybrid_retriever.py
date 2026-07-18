# app/memory/hybrid_retriever.py
"""
Hybrid memory retrieval for JARVIS.

Runs KeywordRetriever and VectorRetriever in parallel,
deduplicates by memory ID, and passes the union to MemoryRanker.

Why both:
- Keyword catches exact matches ("what's my name?" → finds "name: Sajan")
- Vector catches semantic matches ("what do I enjoy?" → finds "I like coding")
- Neither alone is sufficient
"""

from app.memory.schema import Memory
from app.memory.retrieval import KeywordRetriever
from app.memory.vector_retriever import VectorRetriever


class HybridRetriever:
    """
    Combines keyword and vector retrieval.
    Satisfies the CandidateRetriever Protocol — drop-in for either alone.
    """

    def __init__(self, keyword: KeywordRetriever, vector: VectorRetriever):
        self._keyword = keyword
        self._vector = vector

    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]:
        kw_results = self._keyword.find_candidates(query, limit)
        vec_results = self._vector.find_candidates(query, limit)

        # Memory is a mutable dataclass — not hashable, can't use set(memories)
        # Deduplicate by ID instead
        seen: set[str] = set()
        combined: list[Memory] = []

        for memory in kw_results + vec_results:
            if memory.id not in seen:
                seen.add(memory.id)
                combined.append(memory)

        return combined[:limit]

    def on_memory_added(self, memory: Memory) -> None:
        self._keyword.on_memory_added(memory)
        self._vector.on_memory_added(memory)

    def on_memory_removed(self, memory_id: str) -> None:
        self._keyword.on_memory_removed(memory_id)
        self._vector.on_memory_removed(memory_id)

    def on_index_rebuilt(self, memories: list[Memory]) -> None:
        self._keyword.on_index_rebuilt(memories)
        self._vector.on_index_rebuilt(memories)  # single batched embed via VectorRetriever

    def clear(self) -> None:
        self._keyword.clear()
        self._vector.clear()