# app/memory/vector_retriever.py

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from app.config.settings import PathsConfig
from app.memory.schema import Memory

# Backward-compatible defaults; main.py overrides these from Settings.paths.
_DEFAULT_PATHS = PathsConfig()


class VectorRetriever:
    def __init__(
        self,
        persist_dir: str = str(_DEFAULT_PATHS.chroma_dir),
        ollama_url: str = _DEFAULT_PATHS.ollama_url,
        embed_model: str = _DEFAULT_PATHS.embed_model,
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
            documents=[self._memory_to_text(memory)],
            metadatas=[self._to_chroma_meta(memory)],
        )

    def on_memory_removed(self, memory_id: str) -> None:
        try:
            self._collection.delete(ids=[memory_id])
        except Exception:
            pass

    def on_index_rebuilt(self, memories: list[Memory]) -> None:
        # Replace the entire collection in one shot. ChromaDB's embedding
        # function embeds the full document list in a single batched call,
        # instead of the previous per-memory loop that fired one embedding
        # request per memory (O(N) API round-trips on startup / rebuild).
        existing = self._collection.get()
        if existing["ids"]:
            self._collection.delete(ids=existing["ids"])
        if memories:
            self._batch_upsert(memories)

    def _batch_upsert(self, memories: list[Memory]) -> None:
        """Insert/update many memories in a single (batched) call."""
        self._collection.upsert(
            ids=[m.id for m in memories],
            documents=[self._memory_to_text(m) for m in memories],
            metadatas=[self._to_chroma_meta(m) for m in memories],
        )

    def clear(self) -> None:
        existing = self._collection.get()
        if existing["ids"]:
            self._collection.delete(ids=existing["ids"])

    def _to_chroma_meta(self, memory: Memory) -> dict:
        return {
            "id": memory.id,
            "category": memory.category,
            "type": memory.memory_type,
            "value": memory.value,
            "behavior": memory.behavior,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
            "last_used": memory.last_used,
            "source": memory.source,
            "confidence": memory.confidence,
            "importance": memory.importance,
            "access_count": memory.access_count,
        }

    def _memory_to_text(self, memory: Memory) -> str:
        """
        Build the text that gets embedded.
        Richer text = better semantic matching.
        e.g. "preference like: chocolate" embeds better than just "chocolate"
        """
        return f"{memory.category} {memory.memory_type}: {memory.value}"
