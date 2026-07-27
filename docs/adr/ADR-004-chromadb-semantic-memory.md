# ADR-004: ChromaDB Semantic Vector Memory & Hybrid BM25 Retrieval

- **Status**: Evolved into ADR-010
- **Date**: 2026-07-05
- **Version Tag**: `v2.2.0`
- **Commit**: `b2c2211`
- **Confidence**: `VERIFIED`

## Context
Keyword-only memory lookup failed to retrieve semantically related concepts that used different phrasing.

## Decision
Integrate ChromaDB persistent vector database with local `nomic-embed-text` embeddings (`VectorRetriever`) and combine vector similarity scores with BM25 keyword search (`HybridRetriever`).

## Consequences
- **Positive**: High accuracy semantic memory retrieval for complex natural language queries.
- **Negative**: Required local embedding model execution; third-party ChromaDB API was directly coupled to business memory logic.
