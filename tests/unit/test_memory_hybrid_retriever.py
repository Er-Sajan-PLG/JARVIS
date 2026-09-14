"""Unit tests for hybrid retriever in app/memory/hybrid_retriever.py."""

from unittest.mock import MagicMock

import pytest

from app.memory.hybrid_retriever import HybridRetriever
from app.memory.ranking import MemoryRanker
from app.memory.retrieval import KeywordRetriever
from app.memory.schema import Memory
from app.memory.vector_retriever import VectorRetriever


@pytest.fixture
def sample_memories():
    """Create sample Memory objects with distinct IDs and contents."""
    m1 = Memory(
        id="mem-1",
        category="identity",
        memory_type="name",
        value="Sajan",
    )
    m2 = Memory(
        id="mem-2",
        category="preference",
        memory_type="like",
        value="coding in python",
    )
    m3 = Memory(
        id="mem-3",
        category="location",
        memory_type="residence",
        value="Nepal",
    )
    m4 = Memory(
        id="mem-4",
        category="skills",
        memory_type="ability",
        value="design software architectures",
    )
    return {"m1": m1, "m2": m2, "m3": m3, "m4": m4}


def test_hybrid_retriever_find_candidates_deduplication(sample_memories):
    """Verify find_candidates deduplicates results by memory.id via RRF fusion."""
    kw_mock = MagicMock(spec=KeywordRetriever)
    vec_mock = MagicMock(spec=VectorRetriever)

    m1 = sample_memories["m1"]
    m2 = sample_memories["m2"]
    m3 = sample_memories["m3"]

    # Keyword returns [m1, m2]; Vector returns [m2, m3] (m2 is duplicated)
    kw_mock.find_candidates.return_value = [m1, m2]
    vec_mock.find_candidates.return_value = [m2, m3]

    retriever = HybridRetriever(keyword=kw_mock, vector=vec_mock)
    candidates = retriever.find_candidates("who am I", limit=50)

    # m2 appears in both lists, so it fuses to the top; m1 and m3 follow.
    assert len(candidates) == 3
    assert candidates[0] == m2
    assert {c.id for c in candidates} == {"mem-1", "mem-2", "mem-3"}
    kw_mock.find_candidates.assert_called_once_with("who am I", 50)
    vec_mock.find_candidates.assert_called_once_with("who am I", 50)


def test_hybrid_retriever_find_candidates_limit(sample_memories):
    """Verify find_candidates respects the limit parameter."""
    kw_mock = MagicMock(spec=KeywordRetriever)
    vec_mock = MagicMock(spec=VectorRetriever)

    m1 = sample_memories["m1"]
    m2 = sample_memories["m2"]
    m3 = sample_memories["m3"]
    m4 = sample_memories["m4"]

    kw_mock.find_candidates.return_value = [m1, m2]
    vec_mock.find_candidates.return_value = [m3, m4]

    retriever = HybridRetriever(keyword=kw_mock, vector=vec_mock)
    candidates = retriever.find_candidates("test", limit=2)

    assert len(candidates) == 2


def test_hybrid_retriever_empty_results(sample_memories):
    """Verify find_candidates handles empty results from either or both retrievers."""
    kw_mock = MagicMock(spec=KeywordRetriever)
    vec_mock = MagicMock(spec=VectorRetriever)
    retriever = HybridRetriever(keyword=kw_mock, vector=vec_mock)

    # Both empty
    kw_mock.find_candidates.return_value = []
    vec_mock.find_candidates.return_value = []
    assert retriever.find_candidates("query") == []

    # Only vector non-empty
    m1 = sample_memories["m1"]
    vec_mock.find_candidates.return_value = [m1]
    assert retriever.find_candidates("query") == [m1]

    # Only keyword non-empty
    vec_mock.find_candidates.return_value = []
    kw_mock.find_candidates.return_value = [m1]
    assert retriever.find_candidates("query") == [m1]


def test_hybrid_retriever_lifecycle_delegation(sample_memories):
    """Verify lifecycle events are delegated to both keyword and vector retrievers."""
    kw_mock = MagicMock(spec=KeywordRetriever)
    vec_mock = MagicMock(spec=VectorRetriever)
    retriever = HybridRetriever(keyword=kw_mock, vector=vec_mock)

    m = sample_memories["m1"]
    mem_list = [m, sample_memories["m2"]]

    # on_memory_added
    retriever.on_memory_added(m)
    kw_mock.on_memory_added.assert_called_once_with(m)
    vec_mock.on_memory_added.assert_called_once_with(m)

    # on_memory_removed
    retriever.on_memory_removed("mem-1")
    kw_mock.on_memory_removed.assert_called_once_with("mem-1")
    vec_mock.on_memory_removed.assert_called_once_with("mem-1")

    # on_index_rebuilt
    retriever.on_index_rebuilt(mem_list)
    kw_mock.on_index_rebuilt.assert_called_once_with(mem_list)
    vec_mock.on_index_rebuilt.assert_called_once_with(mem_list)

    # clear
    retriever.clear()
    kw_mock.clear.assert_called_once()
    vec_mock.clear.assert_called_once()


def test_hybrid_retriever_ranking_with_stubbed_vector_store(sample_memories):
    """Verify hybrid retriever candidate gathering and subsequent ranking with MemoryRanker."""
    # Real keyword retriever
    kw = KeywordRetriever()
    m_exact = sample_memories["m1"]  # value: "Sajan", type: "name"
    kw.on_memory_added(m_exact)

    # Stubbed vector retriever that found a candidate
    vec_stub = MagicMock(spec=VectorRetriever)
    m_semantic = sample_memories["m2"]  # value: "coding in python"
    vec_stub.find_candidates.return_value = [m_semantic]

    hybrid = HybridRetriever(keyword=kw, vector=vec_stub)
    candidates = hybrid.find_candidates("name", limit=10)

    # Both keyword candidate and vector candidate are retrieved
    assert len(candidates) == 2
    assert m_exact in candidates
    assert m_semantic in candidates

    # Rank with MemoryRanker: rank(candidates, query)
    ranker = MemoryRanker()
    ranked_results = ranker.rank(candidates=candidates, query="name", limit=10)

    assert len(ranked_results) == 2
    # Exact name match should rank first due to higher relevance
    assert ranked_results[0].memory.id == m_exact.id
    assert ranked_results[0].score >= ranked_results[1].score
