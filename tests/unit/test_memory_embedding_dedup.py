"""Tests for embedding-based dedup in the memory subsystem."""

from __future__ import annotations

import pytest

from app.domain import MemoryItem, MemoryKind, MemoryScope
from app.memory.dedup import (
    deduplicate,
    embedding_similarity,
    is_near_duplicate,
    token_similarity,
)


class TestEmbeddingSimilarity:
    def test_identical_vectors_return_one(self):
        v = [1.0, 2.0, 3.0]
        assert embedding_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_return_zero(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert embedding_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors_return_negative(self):
        a = [1.0, 0.0, 0.0]
        b = [-1.0, 0.0, 0.0]
        assert embedding_similarity(a, b) == pytest.approx(-1.0)

    def test_empty_vectors_return_zero(self):
        assert embedding_similarity([], []) == 0.0
        assert embedding_similarity([1.0], []) == 0.0
        assert embedding_similarity([], [1.0]) == 0.0

    def test_different_length_vectors_return_zero(self):
        assert embedding_similarity([1.0, 2.0], [1.0]) == 0.0


class TestTokenSimilarity:
    def test_identical_strings_return_one(self):
        assert token_similarity("hello world", "hello world") == pytest.approx(1.0)

    def test_unrelated_strings_return_low(self):
        assert token_similarity("apple", "zebra") < 0.5

    def test_rephrased_returns_high(self):
        assert token_similarity("I like coffee", "my preference is coffee") > 0.4


class TestIsNearDuplicateWithEmbeddings:
    def test_embedding_match_detected(self):
        """When both items have embeddings and cosine sim >= threshold, it's a duplicate."""
        a = MemoryItem(
            id="1",
            content="I like coffee",
            kind=MemoryKind.PREFERENCE,
            scope=MemoryScope.USER,
            embedding=[1.0, 0.0, 0.0],
        )
        b = MemoryItem(
            id="2",
            content="my preference is coffee",
            kind=MemoryKind.PREFERENCE,
            scope=MemoryScope.USER,
            embedding=[0.95, 0.05, 0.0],
        )
        assert is_near_duplicate(b, [a]) is True

    def test_embedding_mismatch_not_duplicate(self):
        """When embeddings are present but dissimilar, NOT a duplicate."""
        a = MemoryItem(
            id="1",
            content="I like coffee",
            kind=MemoryKind.PREFERENCE,
            scope=MemoryScope.USER,
            embedding=[1.0, 0.0, 0.0],
        )
        b = MemoryItem(
            id="2",
            content="I like tea",
            kind=MemoryKind.PREFERENCE,
            scope=MemoryScope.USER,
            embedding=[0.0, 1.0, 0.0],
        )
        assert is_near_duplicate(b, [a]) is False

    def test_falls_back_to_token_overlap_without_embeddings(self):
        """When no embeddings, uses token-overlap."""
        a = MemoryItem(
            id="1",
            content="I like coffee",
            kind=MemoryKind.PREFERENCE,
            scope=MemoryScope.USER,
        )
        b = MemoryItem(
            id="2",
            content="I like coffee",
            kind=MemoryKind.PREFERENCE,
            scope=MemoryScope.USER,
        )
        assert is_near_duplicate(b, [a]) is True

    def test_same_id_not_duplicate(self):
        """Same ID is not a duplicate of itself."""
        a = MemoryItem(
            id="1",
            content="test",
            kind=MemoryKind.FACT,
            scope=MemoryScope.USER,
            embedding=[1.0, 0.0, 0.0],
        )
        assert is_near_duplicate(a, [a]) is False

    def test_different_scope_not_duplicate(self):
        """Different scope items are not duplicates (same_scope_only=True)."""
        a = MemoryItem(
            id="1",
            content="test",
            kind=MemoryKind.FACT,
            scope=MemoryScope.SESSION,
            embedding=[1.0, 0.0, 0.0],
        )
        b = MemoryItem(
            id="2",
            content="test",
            kind=MemoryKind.FACT,
            scope=MemoryScope.USER,
            embedding=[1.0, 0.0, 0.0],
        )
        assert is_near_duplicate(b, [a]) is False


class TestDeduplicate:
    def test_removes_exact_duplicates(self):
        items = [
            MemoryItem(id="1", content="hello", kind=MemoryKind.FACT, scope=MemoryScope.USER),
            MemoryItem(id="2", content="hello", kind=MemoryKind.FACT, scope=MemoryScope.USER),
        ]
        result = deduplicate(items)
        assert len(result) == 1

    def test_keeps_distinct_items(self):
        items = [
            MemoryItem(id="1", content="hello", kind=MemoryKind.FACT, scope=MemoryScope.USER),
            MemoryItem(id="2", content="world", kind=MemoryKind.FACT, scope=MemoryScope.USER),
        ]
        result = deduplicate(items)
        assert len(result) == 2

    def test_embedding_duplicates_removed(self):
        items = [
            MemoryItem(
                id="1",
                content="I like coffee",
                kind=MemoryKind.PREFERENCE,
                scope=MemoryScope.USER,
                embedding=[1.0, 0.0, 0.0],
            ),
            MemoryItem(
                id="2",
                content="my preference is coffee",
                kind=MemoryKind.PREFERENCE,
                scope=MemoryScope.USER,
                embedding=[0.95, 0.05, 0.0],
            ),
        ]
        result = deduplicate(items)
        assert len(result) == 1
