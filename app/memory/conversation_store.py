# app/memory/conversation_store.py
"""
Embeds and stores conversation exchanges for semantic retrieval.

Separate from fact memory — this stores raw exchanges, not extracted facts.
Lets JARVIS find past conversations by meaning, not just keywords.
"""

import hashlib
import time

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction


class ConversationVectorStore:

    def __init__(
        self,
        persist_dir: str = "data/chroma",
        ollama_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
    ):
        self._embedding_fn = OllamaEmbeddingFunction(
            url=ollama_url,
            model_name=embed_model,
        )
        # Same persist_dir as VectorRetriever — ChromaDB handles
        # multiple collections in the same directory cleanly
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name="jarvis-conversations",       # different collection from jarvis-memories
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def index_history(self, messages: list) -> int:
        """
        One-time bulk import of existing conversation history.
        Pairs user+assistant messages and embeds each pair.
        Returns number of exchanges indexed.
        """
        pairs = self._extract_pairs(messages)
        if not pairs:
            return 0

        for pair_id, user_msg, assistant_msg, timestamp in pairs:
            self._upsert(pair_id, user_msg, assistant_msg, timestamp)

        return len(pairs)

    def add_exchange(
        self, user_msg: str, assistant_msg: str, timestamp: float = None
    ) -> None:
        """Add a single new exchange after it completes."""
        ts = timestamp or time.time()
        pair_id = hashlib.md5(
            f"{ts}{user_msg[:20]}".encode()
        ).hexdigest()[:8]
        self._upsert(pair_id, user_msg, assistant_msg, ts)

    def search(self, query: str, limit: int = 2) -> list[dict]:
        """
        Find past exchanges semantically similar to the query.
        Returns list of {"user": ..., "assistant": ...}
        """
        count = self._collection.count()
        if count == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=min(limit, count),
        )

        exchanges = []
        for metadata in results["metadatas"][0]:
            exchanges.append({
                "user":      metadata["user"],
                "assistant": metadata["assistant"],
            })

        return exchanges

    def count(self) -> int:
        return self._collection.count()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _upsert(
        self, pair_id: str, user_msg: str, assistant_msg: str, timestamp: float
    ) -> None:
        """Store an exchange. The document field is what gets embedded."""
        self._collection.upsert(
            ids=[pair_id],
            documents=[f"User: {user_msg}\nAssistant: {assistant_msg}"],
            metadatas=[{
                "user":      user_msg[:1000],       # cap — ChromaDB metadata limit
                "assistant": assistant_msg[:1000],
                "timestamp": timestamp,
            }],
        )

    def _extract_pairs(self, messages: list) -> list[tuple]:
        """
        Extract user+assistant pairs from a message list.
        Handles both Message objects (from ConversationManager)
        and raw dicts (from conversation.json).
        """
        pairs = []
        i = 0

        while i < len(messages):
            msg = messages[i]

            # Handle both Message dataclass and plain dict
            role    = msg.role    if hasattr(msg, "role")    else msg.get("role", "")
            content = msg.content if hasattr(msg, "content") else msg.get("content", "")

            if role == "user" and i + 1 < len(messages):
                next_msg = messages[i + 1]
                next_role    = next_msg.role    if hasattr(next_msg, "role")    else next_msg.get("role", "")
                next_content = next_msg.content if hasattr(next_msg, "content") else next_msg.get("content", "")

                if next_role == "assistant":
                    ts = getattr(msg, "timestamp", time.time())
                    pair_id = hashlib.md5(
                        f"{ts}{content[:20]}".encode()
                    ).hexdigest()[:8]
                    pairs.append((pair_id, content, next_content, ts))
                    i += 2
                    continue

            i += 1

        return pairs