"""Unit tests for VectorRetriever in app/memory/vector_retriever.py."""

from unittest.mock import MagicMock, patch

import pytest
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from app.memory.schema import Memory
from app.memory.vector_retriever import _DEFAULT_PATHS, VectorRetriever


class DummyEmbeddingFunction(EmbeddingFunction[Documents]):
    """Deterministic in-memory embedding function."""

    def __init__(self):
        pass

    @classmethod
    def name(cls) -> str:
        return "dummy"

    def get_config(self) -> dict:
        return {}

    @classmethod
    def build_from_config(cls, config: dict):
        return cls()

    def __call__(self, input: Documents) -> Embeddings:
        return [[0.1] * 8 for _ in input]


@pytest.fixture
def sample_memory() -> Memory:
    return Memory(
        id="mem-1",
        category="preference",
        memory_type="food",
        value="dark chocolate",
        behavior="append",
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-02T00:00:00",
        last_used="2026-01-03T00:00:00",
        source="user",
        confidence=0.9,
        importance=0.8,
        access_count=5,
    )


@pytest.fixture
def sample_memory_2() -> Memory:
    return Memory(
        id="mem-2",
        category="identity",
        memory_type="name",
        value="JARVIS Assistant",
        behavior="replace",
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-02T00:00:00",
        last_used="2026-01-03T00:00:00",
        source="system",
        confidence=1.0,
        importance=0.95,
        access_count=12,
    )


@pytest.fixture
def retriever(tmp_path) -> VectorRetriever:
    """Fixture providing a VectorRetriever backed by tmp_path and dummy embeddings."""
    with patch(
        "app.memory.vector_retriever.OllamaEmbeddingFunction",
        return_value=DummyEmbeddingFunction(),
    ):
        return VectorRetriever(
            persist_dir=str(tmp_path / "test_chroma"),
            ollama_url="http://mock-ollama:11434",
            embed_model="mock-embed",
        )


def test_init_defaults():
    """Verify VectorRetriever __init__ uses default paths when no parameters given."""
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection

    with (
        patch("app.memory.vector_retriever.OllamaEmbeddingFunction") as mock_embed_cls,
        patch("chromadb.PersistentClient", return_value=mock_client) as mock_client_cls,
    ):
        vr = VectorRetriever()

        mock_embed_cls.assert_called_once_with(
            url=_DEFAULT_PATHS.ollama_url,
            model_name=_DEFAULT_PATHS.embed_model,
        )
        mock_client_cls.assert_called_once_with(path=str(_DEFAULT_PATHS.chroma_dir))
        mock_client.get_or_create_collection.assert_called_once_with(
            name="jarvis-memories",
            embedding_function=mock_embed_cls.return_value,
            metadata={"hnsw:space": "cosine"},
        )
        assert vr._collection is mock_collection


def test_find_candidates_empty_collection(retriever):
    """Verify find_candidates returns empty list when collection has no documents."""
    assert retriever.find_candidates("test query") == []


def test_on_memory_added_and_find_candidates(retriever, sample_memory):
    """Verify adding a memory allows it to be retrieved by find_candidates."""
    retriever.on_memory_added(sample_memory)

    results = retriever.find_candidates("chocolate", limit=10)
    assert len(results) == 1
    retrieved = results[0]
    assert retrieved.id == sample_memory.id
    assert retrieved.category == "preference"
    assert retrieved.memory_type == "food"
    assert retrieved.value == "dark chocolate"
    assert retrieved.confidence == 0.9
    assert retrieved.importance == 0.8
    assert retrieved.access_count == 5


def test_find_candidates_respects_limit(retriever, sample_memory, sample_memory_2):
    """Verify find_candidates limits returned candidates to the limit requested."""
    retriever.on_memory_added(sample_memory)
    retriever.on_memory_added(sample_memory_2)

    assert retriever._collection.count() == 2

    # Query with limit 1
    results = retriever.find_candidates("assistant chocolate", limit=1)
    assert len(results) == 1


def test_find_candidates_skips_malformed_metadata(retriever):
    """Verify corrupted metadata in query results is safely skipped."""
    retriever._collection.count = MagicMock(return_value=2)
    # Return one valid metadata dict and one malformed metadata dict missing required fields
    valid_meta = {
        "id": "mem-valid",
        "category": "pref",
        "type": "item",
        "value": "val",
        "behavior": "append",
        "created_at": "2026-01-01",
        "updated_at": "2026-01-01",
        "last_used": "2026-01-01",
        "source": "user",
        "confidence": 1.0,
        "importance": 0.5,
        "access_count": 0,
    }
    malformed_meta = {"not_a_valid_memory": True}

    retriever._collection.query = MagicMock(
        return_value={"metadatas": [[valid_meta, malformed_meta]]}
    )

    results = retriever.find_candidates("anything", limit=10)
    assert len(results) == 1
    assert results[0].id == "mem-valid"


def test_on_memory_removed_success(retriever, sample_memory):
    """Verify removing a memory deletes it from the collection."""
    retriever.on_memory_added(sample_memory)
    assert retriever._collection.count() == 1

    retriever.on_memory_removed(sample_memory.id)
    assert retriever._collection.count() == 0


def test_on_memory_removed_handles_exception(retriever):
    """Verify on_memory_removed suppresses exceptions raised during delete."""
    retriever._collection.delete = MagicMock(side_effect=RuntimeError("Chroma error"))
    # Should not raise
    retriever.on_memory_removed("non-existent-id")


def test_on_index_rebuilt(retriever, sample_memory, sample_memory_2):
    """Verify on_index_rebuilt clears existing entries and batch-upserts new ones."""
    # Add initial memory
    retriever.on_memory_added(sample_memory)
    assert retriever._collection.count() == 1

    # Rebuild index with sample_memory_2
    retriever.on_index_rebuilt([sample_memory_2])
    assert retriever._collection.count() == 1

    results = retriever.find_candidates("assistant", limit=5)
    assert len(results) == 1
    assert results[0].id == sample_memory_2.id


def test_on_index_rebuilt_empty_memories(retriever, sample_memory):
    """Verify on_index_rebuilt with empty list clears existing entries."""
    retriever.on_memory_added(sample_memory)
    assert retriever._collection.count() == 1

    retriever.on_index_rebuilt([])
    assert retriever._collection.count() == 0


def test_on_index_rebuilt_empty_existing_with_memories(retriever, sample_memory):
    """Verify on_index_rebuilt works when collection is initially empty."""
    assert retriever._collection.count() == 0
    retriever.on_index_rebuilt([sample_memory])
    assert retriever._collection.count() == 1
    assert retriever.find_candidates("chocolate")[0].id == sample_memory.id


def test_clear_non_empty(retriever, sample_memory, sample_memory_2):
    """Verify clear removes all documents from collection."""
    retriever.on_memory_added(sample_memory)
    retriever.on_memory_added(sample_memory_2)
    assert retriever._collection.count() == 2

    retriever.clear()
    assert retriever._collection.count() == 0


def test_clear_already_empty(retriever):
    """Verify clear on empty collection does not fail."""
    assert retriever._collection.count() == 0
    retriever.clear()
    assert retriever._collection.count() == 0


def test_memory_to_text(retriever, sample_memory):
    """Verify _memory_to_text builds the expected text format."""
    text = retriever._memory_to_text(sample_memory)
    assert text == "preference food: dark chocolate"


def test_to_chroma_meta(retriever, sample_memory):
    """Verify _to_chroma_meta contains all required memory fields mapped correctly."""
    meta = retriever._to_chroma_meta(sample_memory)
    assert meta == {
        "id": "mem-1",
        "category": "preference",
        "type": "food",
        "value": "dark chocolate",
        "behavior": "append",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-02T00:00:00",
        "last_used": "2026-01-03T00:00:00",
        "source": "user",
        "confidence": 0.9,
        "importance": 0.8,
        "access_count": 5,
    }
