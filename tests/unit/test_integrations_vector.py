"""Unit tests for app.integrations and app.integrations.vector.chroma."""

from unittest.mock import MagicMock, patch

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

import app.integrations
from app.integrations import ChromaVectorStore, OCRService, get_ocr_service


class DummyEmbeddingFunction(EmbeddingFunction[Documents]):
    """Deterministic dummy embedding function without network dependencies."""

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


def test_integrations_package_exports():
    """Verify app.integrations package exports."""
    assert "OCRService" in app.integrations.__all__
    assert "get_ocr_service" in app.integrations.__all__
    assert "ChromaVectorStore" in app.integrations.__all__
    assert app.integrations.OCRService is OCRService
    assert app.integrations.get_ocr_service is get_ocr_service
    assert app.integrations.ChromaVectorStore is ChromaVectorStore


def test_chroma_vector_store_init_and_crud(tmp_path):
    """Verify ChromaVectorStore CRUD against a temporary local path."""
    with patch(
        "app.integrations.vector.chroma.OllamaEmbeddingFunction",
        return_value=DummyEmbeddingFunction(),
    ):
        store = ChromaVectorStore(
            persist_dir=str(tmp_path / "chroma"),
            collection_name="test-memories",
            ollama_url="http://mock-ollama:11434/api/embeddings",
            embed_model="test-embed",
        )

        assert store.persist_dir == str(tmp_path / "chroma")
        assert store.collection_name == "test-memories"
        assert store.ollama_url == "http://mock-ollama:11434/api/embeddings"
        assert store.embed_model == "test-embed"

        # Initially empty
        assert store.query("anything") == []

        # Upsert
        store.upsert(
            doc_id="doc1",
            document="Alice likes programming",
            metadata={"category": "preference", "user": "Alice"},
        )
        store.upsert(
            doc_id="doc2",
            document="Bob likes mathematics",
            metadata={"category": "preference", "user": "Bob"},
        )

        # Query
        results = store.query("programming", limit=5)
        assert len(results) == 2
        usernames = {r["user"] for r in results}
        assert "Alice" in usernames
        assert "Bob" in usernames

        # Delete
        store.delete("doc1")
        after_delete = store.query("programming", limit=5)
        assert len(after_delete) == 1
        assert after_delete[0]["user"] == "Bob"


def test_chroma_vector_store_query_edge_cases():
    """Verify query() handles count == 0 and empty/None metadatas in results."""
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0

    with (
        patch("chromadb.PersistentClient") as mock_client_cls,
        patch("app.integrations.vector.chroma.OllamaEmbeddingFunction"),
    ):
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_client_cls.return_value = mock_client

        store = ChromaVectorStore(persist_dir="/tmp/mock")
        assert store.query("query", limit=5) == []

        # When count > 0 but metadatas contain None or are empty
        mock_collection.count.return_value = 2
        mock_collection.query.return_value = {"metadatas": [[{"id": "1"}, None, {}]]}
        res = store.query("test", limit=5)
        assert res == [{"id": "1"}]

        # When results has no metadatas key
        mock_collection.query.return_value = {}
        res_empty = store.query("test", limit=5)
        assert res_empty == []


def test_chroma_vector_store_delete_handles_exception():
    """Verify delete() catches exceptions and logs warning rather than raising."""
    mock_collection = MagicMock()
    mock_collection.delete.side_effect = RuntimeError("Delete error")

    with (
        patch("chromadb.PersistentClient") as mock_client_cls,
        patch("app.integrations.vector.chroma.OllamaEmbeddingFunction"),
    ):
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_client_cls.return_value = mock_client

        store = ChromaVectorStore(persist_dir="/tmp/mock")
        # Should not raise
        store.delete("missing_doc")
        mock_collection.delete.assert_called_once_with(ids=["missing_doc"])
