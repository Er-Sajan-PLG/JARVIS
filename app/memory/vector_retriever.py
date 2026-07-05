# app/memory/vector_retriever.py

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from app.memory.schema import Memory


class VectorRetriever:

    def __init__(
        self,
        persist_dir: str = "data/chroma",
        ollama_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
    ):
        embedding_fn = OllamaEmbeddingFunction(
            url=ollama_url,
            model_name=embed_model,
        )

        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name="jarvis-memories",
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]:
        count = self._collection.count()
        if count == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=min(limit, count),
        )

        memories = []
        for metadata in results["metadatas"][0]:
            try:
                memories.append(Memory.from_dict(metadata))
            except Exception:
                pass
        return memories

    def on_memory_added(self, memory: Memory) -> None:
        self._collection.upsert(
            ids=[memory.id],
            documents=[f"{memory.category} {memory.memory_type}: {memory.value}"],
            metadatas=[self._to_chroma_meta(memory)],
        )

    def on_memory_removed(self, memory_id: str) -> None:
        try:
            self._collection.delete(ids=[memory_id])
        except Exception:
            pass

    def on_index_rebuilt(self, memories: list[Memory]) -> None:
        existing = self._collection.get()
        if existing["ids"]:
            self._collection.delete(ids=existing["ids"])
        for memory in memories:
            self.on_memory_added(memory)


        def _memory_to_text(self, memory: Memory) -> str:
            """
            Build the text that gets embedded.
            Richer text = better semantic matching.
            e.g. "preference like: chocolate" embeds better than just "chocolate"
            """
            return f"{memory.category} {memory.memory_type}: {memory.value}"

    def clear(self) -> None:
        existing = self._collection.get()
        if existing["ids"]:
            self._collection.delete(ids=existing["ids"])

    def _to_chroma_meta(self, memory: Memory) -> dict:
        return {
            "id":           memory.id,
            "category":     memory.category,
            "type":         memory.memory_type,
            "value":        memory.value,
            "behavior":     memory.behavior,
            "created_at":   memory.created_at,
            "updated_at":   memory.updated_at,
            "last_used":    memory.last_used,
            "source":       memory.source,
            "confidence":   memory.confidence,
            "importance":   memory.importance,
            "access_count": memory.access_count,
        }