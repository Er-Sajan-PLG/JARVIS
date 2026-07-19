"""
Persistent vector store for ingested papers (the RAG knowledge base).

Wraps a dedicated ChromaDB collection (``jarvis-papers``) that lives alongside
the existing ``jarvis-memories`` and ``jarvis-conversations`` collections in the
same ``data/chroma`` directory. Uses the same ``OllamaEmbeddingFunction``
(``nomic-embed-text``) as the rest of JARVIS so embeddings are consistent.

Each chunk produced by :func:`app.knowledge.chunk.chunk_document` becomes one
ChromaDB record:

    id       = "{doc_id}:{chunk_index}"
    document = chunk.text
    metadata = {
        "doc_id":     <str>,
        "filename":   <str>,
        "title":      <str>,
        "page":       <int>,   # 1-based
        "chunk_index":<int>,   # global 0-based within the document
        "folder":     <str>,   # "" if unfiled; used to scope search/list
    }

The ``doc_id`` is a stable identifier (we use a short hash of the filename)
so an entire document can be deleted without touching others. ``folder`` lets
retrieval be scoped to a single folder (e.g. "Materials Science").
"""

import hashlib
from typing import Optional

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from app.config.settings import PathsConfig
from app.knowledge.chunk import Chunk


# Backward-compatible defaults; the API layer overrides these from Settings.
_DEFAULT_PATHS = PathsConfig()

COLLECTION_NAME = "jarvis-papers"


class PaperStore:
    """ChromaDB-backed store for paper chunks.

    Methods:
        add_document(filename, title, chunks, doc_id=None, folder="") -> doc_id
        search(query, limit, folder=None) -> list[dict]
        list_documents(folder=None) -> list[dict]
        document_count() -> int
        count() -> int
        clear_document(doc_id) -> int   # returns number of chunks removed
    """

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
        # Same persist_dir as the other collections — ChromaDB keeps them
        # isolated by name.
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Write ────────────────────────────────────────────────────────────────

    def add_document(
        self,
        filename: str,
        title: str,
        chunks: list[Chunk],
        doc_id: Optional[str] = None,
        folder: str = "",
    ) -> str:
        """Embed and store all chunks of a document.

        ``doc_id`` namespaces every chunk id as ``"{doc_id}:{chunk_index}"`` so
        an entire document can be cleared later. If ``doc_id`` is not supplied
        it defaults to a stable hash of ``filename`` — so re-ingesting the same
        file (or re-running ingestion) overwrites the prior chunks instead of
        duplicating them. Callers that need multiple versions of the same file
        to coexist should pass an explicit, unique ``doc_id``.

        ``folder`` is stored on every chunk's metadata so retrieval can be
        scoped to a single folder (e.g. "Materials Science") via ``search``.

        Returns the ``doc_id`` used.
        """
        if not chunks:
            raise ValueError("cannot add a document with zero chunks")

        doc_id = doc_id or self._make_doc_id(filename)
        folder = folder or ""

        ids, documents, metadatas = [], [], []
        for chunk in chunks:
            ids.append(f"{doc_id}:{chunk.chunk_index}")
            documents.append(chunk.text)
            metadatas.append({
                "doc_id":      doc_id,
                "filename":    filename,
                "title":       title,
                "page":        int(chunk.page),
                "chunk_index": int(chunk.chunk_index),
                "folder":      folder,
            })

        # upsert so re-ingesting the same doc_id overwrites prior chunks
        self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return doc_id

    def clear_document(self, doc_id: str) -> int:
        """Delete every chunk belonging to ``doc_id``. Returns count removed."""
        ids = self._collection.get(where={"doc_id": doc_id}, include=[])["ids"]
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    # ── Read ─────────────────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 6, folder: Optional[str] = None) -> list[dict]:
        """Semantic search across papers (optionally scoped to ``folder``).

        Returns a list of dicts (most relevant first):
            {"doc_id", "filename", "title", "page", "chunk_index", "folder", "text"}
        """
        count = self._collection.count()
        if count == 0 or not query.strip():
            return []

        where = {"folder": folder} if folder else None
        results = self._collection.query(
            query_texts=[query],
            n_results=min(limit, count),
            where=where,
            include=["documents", "metadatas"],
        )

        out = []
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        for text, meta in zip(docs, metas):
            out.append({
                "doc_id":      meta.get("doc_id", ""),
                "filename":    meta.get("filename", ""),
                "title":       meta.get("title", ""),
                "page":        meta.get("page", 0),
                "chunk_index": meta.get("chunk_index", 0),
                "folder":      meta.get("folder", ""),
                "text":        text,
            })
        return out

    def list_documents(self, folder: Optional[str] = None) -> list[dict]:
        """Return one entry per ingested document.

        Each entry: {"doc_id", "filename", "title", "folder", "chunk_count"}.
        Derived by scanning chunk metadata; cheap for the expected scale.
        Pass ``folder`` to list only documents in that folder.
        """
        result = self._collection.get(include=["metadatas"])
        metas = result.get("metadatas") or []
        if not metas:
            return []

        docs: dict[str, dict] = {}
        for meta in metas:
            doc_id = meta.get("doc_id")
            if doc_id is None:
                continue
            # Folder filter (applied on the dedup key so a doc can live in only
            # one folder at a time in this subsystem).
            if folder is not None and meta.get("folder", "") != folder:
                continue
            entry = docs.get(doc_id)
            if entry is None:
                entry = {
                    "doc_id":      doc_id,
                    "filename":    meta.get("filename", ""),
                    "title":       meta.get("title", ""),
                    "folder":      meta.get("folder", ""),
                    "chunk_count": 0,
                }
                docs[doc_id] = entry
            entry["chunk_count"] += 1

        return list(docs.values())

    def document_count(self) -> int:
        """Number of distinct documents stored."""
        return len(self.list_documents())

    def count(self) -> int:
        """Total number of chunks stored across all documents."""
        return self._collection.count()

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _make_doc_id(filename: str) -> str:
        """Short stable id derived from the filename only.

        Stable per filename so re-ingesting the same file overwrites its prior
        chunks (idempotent ingestion). Unique enough for the expected scale;
        callers needing versioned ids pass an explicit ``doc_id`` to
        :meth:`add_document`.
        """
        return hashlib.sha1(filename.encode()).hexdigest()[:12]
