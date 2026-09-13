# Persistent Memory Subsystem (`app/memory/`) - Version-by-Version History

**Status**: ACTIVE
**Type**: reference
**Last Updated**: 2026-09-13
**Source**: `app/memory/` at HEAD

## Version-by-Version Evolutionary History

### Version v0.5.0 (`4034bf7`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 | Tag Release Date: 2026-06-28*
- **JSON File Store**: `app/memory/store.py` saving extracted user preference strings to disk (`data/memories.json`).

### Version v0.8.0 (`d43f6e9`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 | Tag Release Date: 2026-06-29*
- **Structured Schema & Fact Extraction**: `app/memory/schema.py` introduced structured `Memory` dataclasses with categories (`identity`, `preference`, `project`).

### Version v1.0.0 (`6316917`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 | Tag Release Date: 2026-06-29*
- **Behavior Engine**: `app/memory/manager.py` handling `append`, `replace`, `ignore`, and `delete` memory actions.

### Version v2.2.0 (`b2c2211`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 | Tag Release Date: 2026-07-05*
- **ChromaDB & Hybrid Retrieval**: Added `VectorRetriever` (ChromaDB + `nomic-embed-text`) and `HybridRetriever` (vector similarity + BM25 keyword search).

### Version v3.0.0 Refactored (`8a34243` - `ec0dc4e`) - Current HEAD
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 | Tag Release Date: 2026-07-26*
- **Memory Façade Architecture (`app/memory/`)**:
  - `MemoryService` (`service.py`): Domain-pure façade API adapting internal vector/keyword memory stores to standard `MemoryRecord` domain models.
  - Automatic JSON corruption recovery (`.corrupt-*.bak` quarantine).
- **Active Invariants at HEAD**:
  1. `MemoryService` returns pure `MemoryRecord` domain objects.
  2. Vector store operations isolated in `app/integrations/vector/chroma.py`.
