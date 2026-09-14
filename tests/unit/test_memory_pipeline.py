"""Tests for Sprint 3 memory pipeline enhancements.

Covers the contract-compliant additions:
- MemoryItem domain schema (kind/scope/provenance)
- LLMFactExtractor (LLM-based, kind/scope/confidence classification)
- Near-duplicate detection (dedup)
- Configurable hybrid weighting (0.6 dense / 0.4 sparse)
"""

from datetime import UTC
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.domain import (
    DraftStatus,
    MemoryItem,
    MemoryKind,
    MemoryScope,
)
from app.memory.dedup import deduplicate, is_near_duplicate, token_similarity
from app.memory.hybrid_retriever import DEFAULT_DENSE_WEIGHT, DEFAULT_SPARSE_WEIGHT, HybridRetriever
from app.memory.llm_extractor import LLMFactExtractor

# ---------------------------------------------------------------------------
# MemoryItem domain schema
# ---------------------------------------------------------------------------


class TestMemoryItem:
    def test_defaults(self):
        item = MemoryItem(id="1", content="likes coffee")
        assert item.kind == MemoryKind.FACT
        assert item.scope == MemoryScope.USER
        assert item.draft_status == DraftStatus.CANONICAL
        assert item.confidence == 1.0
        assert item.keywords == []

    def test_is_expired(self):
        from datetime import datetime, timedelta

        past = MemoryItem(id="1", content="x", expires_at=datetime.now(UTC) - timedelta(1))
        assert past.is_expired()
        future = MemoryItem(id="2", content="x", expires_at=datetime.now(UTC) + timedelta(1))
        assert not future.is_expired()
        no_expiry = MemoryItem(id="3", content="x")
        assert not no_expiry.is_expired()

    def test_to_record_projection(self):
        item = MemoryItem(id="m1", content="likes coffee", kind=MemoryKind.PREFERENCE)
        record = item.to_record()
        assert record.id == "m1"
        assert record.value == "likes coffee"


# ---------------------------------------------------------------------------
# Near-duplicate detection
# ---------------------------------------------------------------------------


class TestDedup:
    def test_token_similarity_identical(self):
        assert token_similarity("I like coffee", "I like coffee") == 1.0

    def test_token_similarity_ordering_insensitive(self):
        # Token reordering lowers similarity but stays well above unrelated text.
        assert token_similarity("I like coffee", "coffee I like") < 1.0
        assert token_similarity("I like coffee", "coffee I like") > token_similarity(
            "I like coffee", "the weather today"
        )

    def test_is_near_duplicate_rephrased(self):
        existing = [MemoryItem(id="a", content="I like coffee")]
        dup = MemoryItem(id="b", content="I really like coffee")
        assert is_near_duplicate(dup, existing, threshold=0.7)

    def test_is_near_duplicate_scope_isolated(self):
        existing = [MemoryItem(id="a", content="user is on vacation", scope=MemoryScope.SESSION)]
        candidate = MemoryItem(id="b", content="user is on vacation", scope=MemoryScope.GLOBAL)
        assert not is_near_duplicate(candidate, existing)

    def test_deduplicate_keeps_first(self):
        items = [
            MemoryItem(id="1", content="likes coffee"),
            MemoryItem(id="2", content="likes coffee", confidence=0.5),
            MemoryItem(id="3", content="prefers tea"),
        ]
        result = deduplicate(items, threshold=0.9)
        assert [i.id for i in result] == ["1", "3"]

    def test_deduplicate_no_duplicates(self):
        items = [
            MemoryItem(id="1", content="likes coffee"),
            MemoryItem(id="2", content="works on JARVIS"),
        ]
        result = deduplicate(items)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# LLMFactExtractor
# ---------------------------------------------------------------------------


def _stub_model(raw: str):
    model = MagicMock()
    model.generate.return_value = SimpleNamespace(content=raw)
    return model


class TestLLMFactExtractor:
    def test_extract_parses_json_array(self):
        raw = (
            '[{"content": "user prefers dark mode", "kind": "preference", '
            '"scope": "user", "confidence": 0.9}]'
        )
        extractor = LLMFactExtractor(_stub_model(raw))
        items = extractor.extract("I prefer dark mode")
        assert len(items) == 1
        assert items[0].content == "user prefers dark mode"
        assert items[0].kind == MemoryKind.PREFERENCE
        assert items[0].scope == MemoryScope.USER
        assert items[0].confidence == pytest.approx(0.9)

    def test_extract_strips_markdown_fence(self):
        raw = (
            "```json\n"
            '[{"content": "a fact", "kind": "fact", "scope": "global", "confidence": 1.0}]\n'
            "```"
        )
        extractor = LLMFactExtractor(_stub_model(raw))
        items = extractor.extract("a fact")
        assert len(items) == 1
        assert items[0].kind == MemoryKind.FACT
        assert items[0].scope == MemoryScope.GLOBAL

    def test_extract_empty_message(self):
        extractor = LLMFactExtractor(_stub_model("[]"))
        assert extractor.extract("") == []

    def test_extract_unparseable_returns_empty(self):
        extractor = LLMFactExtractor(_stub_model("not json at all"))
        assert extractor.extract("hello") == []

    def test_extract_invalid_kind_falls_back_to_fact(self):
        raw = '[{"content": "x", "kind": "bogus", "scope": "user", "confidence": 0.5}]'
        extractor = LLMFactExtractor(_stub_model(raw))
        items = extractor.extract("x")
        assert items[0].kind == MemoryKind.FACT

    def test_extract_clamps_confidence(self):
        raw = '[{"content": "x", "kind": "fact", "scope": "user", "confidence": 5.0}]'
        extractor = LLMFactExtractor(_stub_model(raw))
        items = extractor.extract("x")
        assert items[0].confidence == 1.0

    def test_extract_attaches_source_and_draft_status(self):
        raw = '[{"content": "x", "kind": "fact", "scope": "user", "confidence": 1.0}]'
        extractor = LLMFactExtractor(_stub_model(raw))
        items = extractor.extract("x", source="tool", session_id="s1")
        assert items[0].source == "tool"
        assert items[0].draft_status == DraftStatus.DRAFT
        assert items[0].metadata["session_id"] == "s1"


# ---------------------------------------------------------------------------
# HybridRetriever configurable weights
# ---------------------------------------------------------------------------


class _FakeKeyword:
    def __init__(self, results):
        self._results = results

    def find_candidates(self, query, limit=50):
        return self._results[:limit]

    def on_memory_added(self, m):
        pass

    def on_memory_removed(self, i):
        pass

    def on_index_rebuilt(self, ms):
        pass

    def clear(self):
        pass


class _FakeVector(_FakeKeyword):
    pass


def _mem(mid):
    return SimpleNamespace(id=mid)


class TestHybridRetriever:
    def test_default_weights(self):
        kw = _FakeKeyword([_mem("a"), _mem("b")])
        vec = _FakeVector([_mem("c"), _mem("d")])
        hr = HybridRetriever(kw, vec)
        assert hr.weights == (DEFAULT_DENSE_WEIGHT, DEFAULT_SPARSE_WEIGHT)

    def test_fuse_combines_and_dedupes(self):
        kw = _FakeKeyword([_mem("a"), _mem("shared")])
        vec = _FakeVector([_mem("shared"), _mem("b")])
        hr = HybridRetriever(kw, vec)
        result = hr.find_candidates("q", limit=10)
        ids = [m.id for m in result]
        assert "shared" in ids
        assert len(ids) == len(set(ids))  # no duplicates
        assert len(ids) == 3  # a, shared, b

    def test_set_weights(self):
        kw = _FakeKeyword([])
        vec = _FakeVector([])
        hr = HybridRetriever(kw, vec)
        hr.set_weights(0.5, 0.5)
        assert hr.weights == (0.5, 0.5)

    def test_set_weights_rejects_both_zero(self):
        hr = HybridRetriever(_FakeKeyword([]), _FakeVector([]))
        with pytest.raises(ValueError):
            hr.set_weights(0.0, 0.0)

    def test_fuse_prefers_item_high_in_both(self):
        # "shared" is rank 0 in dense and rank 0 in sparse -> strongest.
        kw = _FakeKeyword([_mem("shared"), _mem("kw_only")])
        vec = _FakeVector([_mem("shared"), _mem("vec_only")])
        hr = HybridRetriever(kw, vec)
        result = hr.find_candidates("q", limit=10)
        assert result[0].id == "shared"
