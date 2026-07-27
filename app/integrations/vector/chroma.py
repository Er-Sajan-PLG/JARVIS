"""ChromaDB Vector Store Integration Wrapper.

Wraps chromadb PersistentClient and embedding functions behind clean vector search interfaces.
"""

import logging
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """Wrapper isolating ChromaDB vector storage and embedding generation."""

    def __init__(
        self,
        persist_dir: str = "data/chroma",
        collection_name: str = "jarvis-memories",
        ollama_url: str = "http://localhost:11434/api/embeddings",
        embed_model: str = "nomic-embed-text",
    ) -> None:
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.ollama_url = ollama_url
        self.embed_model = embed_model

        embedding_fn = OllamaEmbeddingFunction(
            url=self.ollama_url,
            model_name=self.embed_model,
        )

        self._client = chromadb.PersistentClient(path=self.persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Initialized ChromaVectorStore at '%s'", self.persist_dir)

    def query(self, text: str, limit: int = 10) -> list[dict[str, Any]]:
        """Query vector database for nearest neighbors.

        Args:
            text: Query prompt text.
            limit: Max results count.

        Returns:
            List of metadata dictionaries.
        """
        count = self._collection.count()
        if count == 0:
            return []

        results = self._collection.query(
            query_texts=[text],
            n_results=min(limit, count),
        )

        metadatas: list[dict[str, Any]] = []
        if results and "metadatas" in results and results["metadatas"]:
            for meta in results["metadatas"][0]:
                if meta:
                    metadatas.append(meta)
        return metadatas

    def upsert(self, doc_id: str, document: str, metadata: dict[str, Any]) -> None:
        """Upsert a document into vector store."""
        self._collection.upsert(
            ids=[doc_id],
            documents=[document],
            metadatas=[metadata],
        )

    def delete(self, doc_id: str) -> None:
        """Delete a document by ID."""
        try:
            self._collection.delete(ids=[doc_id])
        except Exception as err:
            logger.warning("Failed to delete vector document '%s': %s", doc_id, err)
