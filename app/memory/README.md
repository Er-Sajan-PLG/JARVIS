# app/memory

<!-- generated:module_readmes begin -->

| Module | Purpose | Top-level API |
|---|---|---|
| `__init__.py` | JARVIS Memory Package. | — |
| `conversation_store.py` | Embeds and stores conversation exchanges for semantic retrieval. | `ConversationVectorStore` |
| `dedup.py` | Near-duplicate detection for the memory pipeline (Sprint 3 contract §2). | `_get_embedding()`, `_get_model()`, `_normalize()`, `deduplicate()`, `embedding_similarity()`, `is_near_duplicate()`, `token_similarity()` |
| `fact_extractor.py` | Fact Extractor for JARVIS v2.0 | `_extract_value()`, `_split_into_sentences()`, `extract_facts()` |
| `hybrid_retriever.py` | Hybrid memory retrieval for JARVIS. | `HybridRetriever` |
| `llm_extractor.py` | LLM-backed fact extraction for the memory pipeline (Sprint 3 contract §2). | `ChatModel`, `LLMFactExtractor` |
| `manager.py` | Memory Manager for JARVIS v2.0 | `MemoryManager` |
| `pipeline.py` | Memory pipeline — unified extract → manage → store → retrieve flow. | `MemoryPipeline`, `_scope_of()` |
| `ranking.py` | Memory Ranking for JARVIS v2.0 | `MemoryRanker`, `RankingWeights` |
| `retrieval.py` | Candidate Retrieval for JARVIS v2.0 | `CandidateRetriever`, `KeywordRetriever` |
| `rules.py` | (no module docstring) | — |
| `schema.py` | Memory schema definitions for JARVIS v2.0 | `Memory`, `MemoryResult` |
| `service.py` | Persistent Memory Façade. | `MemoryService`, `_is_storable()` |
| `store.py` | Memory Store for JARVIS v2.0 | `MemoryStore`, `_validate_field_value()` |
| `temporal.py` | Bi-temporal memory: two clocks, invalidation instead of deletion. | `Resolution`, `TemporalFact`, `_ts()`, `close_interval()`, `find_superseded_by()`, `format_occurs_at()`, `has_occurred()`, `is_valid_at()` |
| `vector_retriever.py` | (no module docstring) | `VectorRetriever` |

<!-- generated:module_readmes end -->
