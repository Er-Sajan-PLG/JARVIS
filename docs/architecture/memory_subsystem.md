# Memory Subsystem Architecture (`v3.0.0 Refactored`)

> **Source of Truth**: `app/memory/` and `app/integrations/vector/` at `HEAD`.
> **Timeline Metadata**: *Feature Author Date: 2026-07-28 (`8a34243`) | Tag Release Date: 2026-07-28*

---

## 1. Hybrid Search & Memory Façade

```mermaid
flowchart TB
    CALLER["Cognitive Brain / ContextBuilder"] --> SERVICE["MemoryService Façade<br/>(app/memory/service.py)"]
    
    SERVICE --> STORE["MemoryStore (BM25 / Keyword)<br/>(app/memory/store.py)"]
    SERVICE --> CHROMA["ChromaVectorStore (Semantic)<br/>(app/integrations/vector/chroma.py)"]
    
    STORE --> FILE["data/memories.json"]
    CHROMA --> DB["data/chroma/"]
```
