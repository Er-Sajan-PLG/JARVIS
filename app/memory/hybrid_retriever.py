# app/memory/hybrid_retriever.py
"""
Hybrid memory retrieval for JARVIS.

Runs KeywordRetriever (sparse/BM25-like) and VectorRetriever (dense/embeddings)
in parallel, fuses their result lists by **configurable** weights
(Sprint 3 contract: 0.6 dense / 0.4 sparse by default), deduplicates by memory
ID, and passes the fused union to MemoryRanker for final scoring.

Weighting uses reciprocal rank fusion (RRF): each retriever contributes
``weight / (k + rank)`` per candidate, so a memory that appears high in both
lists outranks one that appears in only one.
"""

from app.memory.retrieval import CandidateRetriever
from app.memory.schema import Memory

# Contract-default weights: dense (vector) is the stronger signal.
DEFAULT_DENSE_WEIGHT = 0.6
DEFAULT_SPARSE_WEIGHT = 0.4
# RRF smoothing constant.
_DEFAULT_K = 60.0


class HybridRetriever:
    """
    Combines keyword and vector retrieval with configurable weights.
    Satisfies the CandidateRetriever Protocol — drop-in for either alone.
    """

    def __init__(
        self,
        keyword: CandidateRetriever,
        vector: CandidateRetriever,
        dense_weight: float = DEFAULT_DENSE_WEIGHT,
        sparse_weight: float = DEFAULT_SPARSE_WEIGHT,
        k: float = _DEFAULT_K,
    ):
        self._keyword = keyword
        self._vector = vector
        self._dense_weight = dense_weight
        self._sparse_weight = sparse_weight
        self._k = k

    @property
    def weights(self) -> tuple[float, float]:
        """The current (dense, sparse) fusion weights."""
        return (self._dense_weight, self._sparse_weight)

    def set_weights(self, dense_weight: float, sparse_weight: float) -> None:
        """Reconfigure the hybrid fusion weights at runtime."""
        if dense_weight < 0 or sparse_weight < 0:
            raise ValueError("weights must be non-negative")
        if dense_weight + sparse_weight == 0:
            raise ValueError("weights must not both be zero")
        self._dense_weight = dense_weight
        self._sparse_weight = sparse_weight

    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]:
        kw_results = self._keyword.find_candidates(query, limit)
        vec_results = self._vector.find_candidates(query, limit)
        return self._fuse(kw_results, vec_results, limit)

    def _fuse(
        self,
        sparse: list[Memory],
        dense: list[Memory],
        limit: int,
    ) -> list[Memory]:
        """Fuse sparse+dense lists via weighted reciprocal rank fusion."""
        scores: dict[str, float] = {}
        order: dict[str, Memory] = {}

        for rank, memory in enumerate(dense):
            scores[memory.id] = scores.get(memory.id, 0.0) + self._dense_weight / (
                self._k + rank + 1
            )
            order[memory.id] = memory
        for rank, memory in enumerate(sparse):
            scores[memory.id] = scores.get(memory.id, 0.0) + self._sparse_weight / (
                self._k + rank + 1
            )
            order.setdefault(memory.id, memory)

        ranked_ids = sorted(scores, key=lambda mid: scores[mid], reverse=True)
        return [order[mid] for mid in ranked_ids[:limit]]

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
