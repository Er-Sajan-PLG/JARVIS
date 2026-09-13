"""Unit tests for MemoryManager in app/memory/manager.py."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.config.settings import MemoryConfig
from app.memory.manager import MemoryManager
from app.memory.ranking import MemoryRanker, RankingWeights
from app.memory.retrieval import KeywordRetriever
from app.memory.schema import (
    BEHAVIOR_APPEND,
    BEHAVIOR_DELETE,
    BEHAVIOR_IGNORE,
    BEHAVIOR_REPLACE,
    IMPORTANCE_HIGH,
    IMPORTANCE_MEDIUM,
    SOURCE_USER,
    MemoryResult,
)


@pytest.fixture
def mem_dir(tmp_path: Path) -> Path:
    return tmp_path / "memories.json"


@pytest.fixture
def mock_retriever():
    retriever = MagicMock(spec=KeywordRetriever)
    retriever.find_candidates.return_value = []
    return retriever


@pytest.fixture
def mock_ranker():
    ranker = MagicMock(spec=MemoryRanker)
    ranker.rank.return_value = []
    return ranker


@pytest.fixture
def manager(mem_dir: Path, mock_retriever, mock_ranker) -> MemoryManager:
    config = MemoryConfig(retrieval_limit=5, min_relevance_score=0.3)
    return MemoryManager(
        path=str(mem_dir),
        config=config,
        retriever=mock_retriever,
        ranker=mock_ranker,
    )


# ===== Initialization Tests =====


def test_init_defaults(tmp_path: Path):
    """Verify MemoryManager initializes with default dependencies if none provided."""
    mem_file = tmp_path / "default_mem.json"
    mgr = MemoryManager(path=str(mem_file))

    assert mgr.config is not None
    assert isinstance(mgr._retriever, KeywordRetriever)
    assert isinstance(mgr._ranker, MemoryRanker)
    assert mgr.count() == 0


def test_init_custom_weights(tmp_path: Path, mock_retriever):
    """Verify ranking_weights parameter is passed to ranker during initialization."""
    mem_file = tmp_path / "weights_mem.json"
    weights = RankingWeights(relevance=0.8, recency=0.1, importance=0.1)
    mgr = MemoryManager(
        path=str(mem_file),
        retriever=mock_retriever,
        ranking_weights=weights,
    )
    assert mgr._ranker.weights.relevance == 0.8
    mock_retriever.on_index_rebuilt.assert_called_once()


# ===== Store and Behavior Tests =====


def test_store_behavior_ignore(manager):
    """Verify BEHAVIOR_IGNORE returns None and does not store anything."""
    fact = {
        "category": "temp",
        "type": "weather",
        "value": "sunny",
        "behavior": BEHAVIOR_IGNORE,
    }
    result = manager.store(fact)
    assert result is None
    assert manager.count() == 0


def test_store_behavior_delete(manager):
    """Verify BEHAVIOR_DELETE deletes matching category/type and returns None."""
    # Seed a memory
    manager.store(
        {
            "category": "preference",
            "type": "theme",
            "value": "dark",
        }
    )
    assert manager.count() == 1

    # Delete via store()
    fact = {
        "category": "preference",
        "type": "theme",
        "behavior": BEHAVIOR_DELETE,
    }
    result = manager.store(fact)
    assert result is None
    assert manager.count() == 0


def test_store_behavior_append(manager, mock_retriever):
    """Verify BEHAVIOR_APPEND creates, indexes, and persists a new memory."""
    stored_callbacks = []
    manager.on_store(lambda m: stored_callbacks.append(m))

    fact = {
        "category": "preference",
        "type": "food",
        "value": "pizza",
        "behavior": BEHAVIOR_APPEND,
        "confidence": 0.95,
        "importance": IMPORTANCE_HIGH,
        "metadata": {"source_detail": "chat"},
    }
    mem = manager.store(fact, source="agent")

    assert mem is not None
    assert mem.category == "preference"
    assert mem.memory_type == "food"
    assert mem.value == "pizza"
    assert mem.behavior == BEHAVIOR_APPEND
    assert mem.source == "agent"
    assert mem.confidence == 0.95
    assert mem.importance == IMPORTANCE_HIGH
    assert mem.metadata == {"source_detail": "chat"}

    assert manager.count() == 1
    mock_retriever.on_memory_added.assert_called_once_with(mem)
    assert stored_callbacks == [mem]


def test_store_default_behavior_and_minimal_fact(manager):
    """Verify default behavior is APPEND and defaults are used for missing fields."""
    fact = {
        "category": "identity",
        "type": "name",
        "value": "Alice",
    }
    mem = manager.store(fact)

    assert mem.behavior == BEHAVIOR_APPEND
    assert mem.source == SOURCE_USER
    assert mem.confidence == 1.0
    assert mem.importance == IMPORTANCE_MEDIUM
    assert mem.metadata == {}
    assert manager.count() == 1


def test_store_behavior_replace_no_existing(manager):
    """Verify BEHAVIOR_REPLACE appends when no matching memory exists."""
    fact = {
        "category": "preference",
        "type": "beverage",
        "value": "tea",
        "behavior": BEHAVIOR_REPLACE,
    }
    mem = manager.store(fact)
    assert mem.value == "tea"
    assert manager.count() == 1


def test_store_behavior_replace_existing(manager):
    """Verify BEHAVIOR_REPLACE updates existing memory and fires on_update."""
    update_callbacks = []
    manager.on_update(lambda m: update_callbacks.append(m))

    # First store
    first = manager.store(
        {
            "category": "preference",
            "type": "beverage",
            "value": "coffee",
            "confidence": 0.8,
            "importance": 0.5,
        }
    )
    initial_id = first.id

    # Now replace with all fields updated
    second = manager.store(
        {
            "category": "preference",
            "type": "beverage",
            "value": "green tea",
            "behavior": BEHAVIOR_REPLACE,
            "confidence": 0.99,
            "importance": 0.9,
            "metadata": {"updated_via": "test"},
        },
        source="assistant",
    )

    assert manager.count() == 1
    assert second.id == initial_id
    assert second.value == "green tea"
    assert second.source == "assistant"
    assert second.confidence == 0.99
    assert second.importance == 0.9
    assert second.behavior == BEHAVIOR_REPLACE
    assert second.metadata == {"updated_via": "test"}
    assert update_callbacks == [second]


def test_replace_convenience_method(manager):
    """Verify replace() calls _handle_replace directly."""
    mem = manager.replace(
        {
            "category": "location",
            "type": "city",
            "value": "Kathmandu",
        }
    )
    assert mem.value == "Kathmandu"

    replaced = manager.replace(
        {
            "category": "location",
            "type": "city",
            "value": "Pokhara",
        }
    )
    assert replaced.id == mem.id
    assert replaced.value == "Pokhara"


# ===== Retrieve Tests =====


def test_retrieve_pipeline_with_results(manager, mock_retriever, mock_ranker):
    """Verify retrieve queries retriever, ranks candidates, and touches returned memories."""
    # Seed memories
    mem1 = manager.store({"category": "c1", "type": "t1", "value": "v1"})
    mem2 = manager.store({"category": "c2", "type": "t2", "value": "v2"})
    assert mem1.access_count == 0
    assert mem2.access_count == 0

    mock_retriever.find_candidates.return_value = [mem1, mem2]
    ranked_result = MemoryResult(memory=mem1, score=0.92)
    mock_ranker.rank.return_value = [ranked_result]

    results = manager.retrieve("query text", limit=2)

    assert results == [ranked_result]
    # mem1 should be touched (access_count incremented, last_used updated)
    assert mem1.access_count == 1
    assert mem2.access_count == 0

    # Check retriever was called with candidate overshoot (min(limit*3, count or 50))
    # limit=2, limit*3=6, count=2 => min(6, 2) = 2
    mock_retriever.find_candidates.assert_called_once_with("query text", limit=2)
    mock_ranker.rank.assert_called_once_with(
        candidates=[mem1, mem2],
        query="query text",
        limit=2,
        min_score=manager.config.min_relevance_score,
    )


def test_retrieve_empty_results(manager, mock_retriever, mock_ranker):
    """Verify retrieve handles empty candidates/results gracefully without calling force_save."""
    mock_retriever.find_candidates.return_value = []
    mock_ranker.rank.return_value = []

    results = manager.retrieve("some query")
    assert results == []


def test_retrieve_uses_config_default_limit(manager, mock_retriever, mock_ranker):
    """Verify retrieve defaults limit to config.retrieval_limit when limit=None."""
    mock_retriever.find_candidates.return_value = []
    mock_ranker.rank.return_value = []

    manager.retrieve("query", limit=None)
    mock_ranker.rank.assert_called_once_with(
        candidates=[],
        query="query",
        limit=manager.config.retrieval_limit,
        min_score=manager.config.min_relevance_score,
    )


# ===== Update and Merge Tests =====


def test_update_existing_memory(manager):
    """Verify update applies field updates, fires callback, and saves."""
    mem = manager.store({"category": "cat", "type": "typ", "value": "initial"})
    callbacks = []
    manager.on_update(lambda m: callbacks.append(m))

    updated = manager.update(mem.id, {"value": "modified", "confidence": 0.75})
    assert updated is not None
    assert updated.value == "modified"
    assert updated.confidence == 0.75
    assert callbacks == [updated]


def test_update_non_existing_memory(manager):
    """Verify update returns None if memory does not exist."""
    callbacks = []
    manager.on_update(lambda m: callbacks.append(m))

    res = manager.update("missing-id", {"value": "val"})
    assert res is None
    assert len(callbacks) == 0


def test_merge_existing_memory_append_value(manager):
    """Verify merge appends new value if not already in existing memory."""
    mem = manager.store({"category": "skills", "type": "prog", "value": "Python"})
    merged = manager.merge(mem.id, {"value": "Rust"})

    assert merged is not None
    assert merged.value == "Python; Rust"


def test_merge_existing_memory_duplicate_value(manager):
    """Verify merge updates value directly if already substring in existing memory."""
    mem = manager.store({"category": "skills", "type": "prog", "value": "Python; Rust"})
    merged = manager.merge(mem.id, {"value": "Python"})

    assert merged is not None
    assert merged.value == "Python"


def test_merge_existing_memory_without_value(manager):
    """Verify merge preserves existing value if new_data has no value field."""
    mem = manager.store({"category": "skills", "type": "prog", "value": "Python"})
    merged = manager.merge(mem.id, {"importance": 0.95})

    assert merged is not None
    assert merged.value == "Python"
    assert merged.importance == 0.95


def test_merge_does_not_mutate_caller_dict(manager):
    """Verify merge does not mutate the dictionary passed by caller."""
    mem = manager.store({"category": "skills", "type": "prog", "value": "Go"})
    caller_dict = {"value": "TypeScript", "confidence": 0.8}

    manager.merge(mem.id, caller_dict)
    assert caller_dict == {"value": "TypeScript", "confidence": 0.8}


def test_merge_non_existing_memory(manager):
    """Verify merge on non-existing memory delegates to update and returns None."""
    res = manager.merge("non-existent-id", {"value": "something"})
    assert res is None


# ===== Delete Tests =====


def test_delete_existing_memory(manager, mock_retriever):
    """Verify delete removes memory from store and retriever, and fires callback."""
    mem = manager.store({"category": "temp", "type": "del", "value": "val"})
    deleted_callbacks = []
    manager.on_delete(lambda m: deleted_callbacks.append(m))

    success = manager.delete(mem.id)
    assert success is True
    assert manager.count() == 0
    mock_retriever.on_memory_removed.assert_called_once_with(mem.id)
    assert deleted_callbacks == [mem]


def test_delete_non_existing_memory(manager, mock_retriever):
    """Verify delete returns False when memory is not found."""
    assert manager.delete("not-here") is False
    mock_retriever.on_memory_removed.assert_not_called()


def test_delete_by_type_matches(manager, mock_retriever):
    """Verify delete_by_type removes all matching memories and returns count."""
    m1 = manager.store({"category": "catA", "type": "typeX", "value": "v1"})
    m2 = manager.store({"category": "catA", "type": "typeX", "value": "v2"})
    m3 = manager.store({"category": "catA", "type": "typeY", "value": "v3"})

    deleted_callbacks = []
    manager.on_delete(lambda m: deleted_callbacks.append(m))

    removed_count = manager.delete_by_type("catA", "typeX")
    assert removed_count == 2
    assert manager.count() == 1
    assert manager.get_by_id(m3.id) is not None

    assert mock_retriever.on_memory_removed.call_count == 2
    assert [m.id for m in deleted_callbacks] == [m1.id, m2.id]


def test_delete_by_type_no_match(manager, mock_retriever):
    """Verify delete_by_type returns 0 when no memories match."""
    removed_count = manager.delete_by_type("nonexistent", "none")
    assert removed_count == 0
    mock_retriever.on_memory_removed.assert_not_called()


# ===== Query, Persistence, and State Tests =====


def test_query_methods(manager):
    """Verify get_all, get_by_category, get_by_type, get_by_id, and count."""
    m1 = manager.store({"category": "cat1", "type": "t1", "value": "v1"})
    m2 = manager.store({"category": "cat1", "type": "t2", "value": "v2"})
    manager.store({"category": "cat2", "type": "t1", "value": "v3"})

    assert len(manager.get_all()) == 3
    assert len(manager.get_by_category("cat1")) == 2
    assert len(manager.get_by_category("cat2")) == 1
    assert len(manager.get_by_category("cat3")) == 0

    assert len(manager.get_by_type("cat1", "t1")) == 1
    assert manager.get_by_type("cat1", "t1")[0].id == m1.id
    assert len(manager.get_by_type("cat1", "t3")) == 0

    assert manager.get_by_id(m2.id) == m2
    assert manager.get_by_id("no-such-id") is None

    assert manager.count() == 3


def test_is_dirty_and_persistence(manager):
    """Verify is_dirty, save, and save_if_dirty pass-throughs."""
    assert manager.is_dirty is False
    manager._store._dirty = True
    assert manager.is_dirty is True

    manager.save()
    assert manager.is_dirty is False

    manager._store._dirty = True
    manager.save_if_dirty()
    assert manager.is_dirty is False


def test_clear(manager, mock_retriever):
    """Verify clear removes memories from store and clears retriever."""
    manager.store({"category": "c", "type": "t", "value": "v"})
    assert manager.count() == 1

    manager.clear()
    assert manager.count() == 0
    mock_retriever.clear.assert_called_once()


# ===== Legacy Compatibility Tests =====


def test_legacy_compatibility(manager):
    """Verify facts property, load method, and add_fact method."""
    manager.add_fact({"category": "c", "type": "t", "value": "val"})
    assert manager.count() == 1

    facts = manager.facts
    assert isinstance(facts, list)
    assert len(facts) == 1
    assert facts[0]["category"] == "c"
    assert facts[0]["value"] == "val"

    conv, loaded_facts = manager.load()
    assert conv == []
    assert loaded_facts == facts
