"""Vector Integration Package.

Provides vector search database wrappers isolating third-party vector backends (ChromaDB, pgvector).
"""

from app.integrations.vector.chroma import ChromaVectorStore

__all__ = ["ChromaVectorStore"]
