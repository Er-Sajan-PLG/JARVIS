# JARVIS — Memory Subsystem

> Module: `app/memory/`. The memory subsystem has **two distinct stores**: the
> fact store (`MemoryManager` + `MemoryStore`, JSON-persisted) and the
> conversation history store (`ConversationVectorStore`, ChromaDB-persisted).
> They are never merged and never share a schema.

---

## 1. Memory Component Overview

```mermaid
flowchart TB
    subgraph FACADE["Public Façade (only external entry point)"]
        MM["MemoryManager<br/>store / retrieve / delete / merge / update"]
    end

    subgraph STORE["Fact Store (app/memory)"]
        STORE2["MemoryStore<br/>CRUD + JSON persistence<br/>data/memories.json"]
        RET["HybridRetriever<br/>CandidateRetriever Protocol"]
        KW["KeywordRetriever<br/>Jaccard keyword overlap"]
        VEC["VectorRetriever<br/>ChromaDB cosine"]
        RANK["MemoryRanker<br/>relevance + importance + freq + recency + conf"]
        RULES["RULES<br/>trigger -> category/type/behavior"]
    end

    subgraph HIST["Conversation History (separate store)"]
        CVS["ConversationVectorStore<br/>ChromaDB embeddings of exchanges"]
    end

    subgraph SCHEMA["Data Contracts"]
        MEM["Memory dataclass"]
        MRES["MemoryResult (memory + score)"]
    end

    EXTRACT["extract_facts()"] -->|"list[dict]"| MM
    MM --> STORE2
    MM --> RET
    MM --> RANK
    RET --> KW
    RET --> VEC
    KW --> STORE2
    VEC --> STORE2
    RANK --> MRES
    STORE2 --> MEM
    MM --> CVS
```

**One responsibility each:**
- `MemoryManager` — orchestration + *behavior* logic (append/replace/ignore/delete).
- `MemoryStore` — pure CRUD + persistence (no business logic).
- `KeywordRetriever` / `VectorRetriever` / `HybridRetriever` — candidate search only.
- `MemoryRanker` — scoring only.
- `fact_extractor` + `rules` — message→fact transformation only.

---

## 2. Store (write) Flow

What happens when a fact is stored. Behavior is resolved in the manager, never
in the store.

```mermaid
flowchart TB
    IN["memory.store(fact, source)"] --> BEH{"behavior?"}

    BEH -->|"ignore"| IGN["return None"]
    BEH -->|"delete"| DEL["delete_by_type(category, type)"]
    BEH -->|"replace"| REP["_handle_replace<br/>find match -> overwrite value"]
    BEH -->|"append (default)"| APP["_handle_append<br/>new Memory + add"]

    APP --> ADD["store.add(memory)"]
    REP --> UPD["store.update_fields / overwrite"]
    DEL --> RM["store.remove_by_category_and_type"]

    ADD --> IDX["retriever.on_memory_added(memory)"]
    UPD --> IDX
    RM --> RMIDX["retriever.on_memory_removed(id)"]

    IDX --> SAVE["store.save() / force_save()"]
    RMIDX --> SAVE
    SAVE --> JSON["data/memories.json"]
    IDX --> CHR["ChromaDB upsert (vector)"]
```

---

## 3. Retrieve (read) Flow

What happens on `memory.retrieve(prompt, limit)`.

```mermaid
flowchart TB
    R["memory.retrieve(prompt, limit)"] --> CAND["retriever.find_candidates<br/>(overshoot: limit * 3)"]
    CAND --> HYB{"HybridRetriever"}
    HYB --> KW["KeywordRetriever.find_candidates"]
    HYB --> VEC["VectorRetriever.find_candidates<br/>(ChromaDB query)"]
    KW --> UNION["dedupe by memory.id"]
    VEC --> UNION
    UNION --> RANK["MemoryRanker.rank<br/>(weighted score)"]
    RANK --> FILT["filter min_relevance_score"]
    FILT --> TOUCH["touch() each returned memory<br/>(updates last_used + access_count)"]
    TOUCH --> OUT["list[MemoryResult]"]
    TOUCH --> PERSIST["store.force_save()"]
```

---

## 4. Persistence Layout

Two independent persistence mechanisms.

```mermaid
flowchart LR
    subgraph FACTS["Fact Store"]
        MS["MemoryStore"] -->|"JSON"| FJ["data/memories.json<br/>{version, memories[]}"]
        VEC2["VectorRetriever"] -->|"vectors"| CHR["ChromaDB<br/>collection: jarvis-memories"]
    end
    subgraph HIST["History Store"]
        CVS["ConversationVectorStore"] -->|"vectors"| CHR2["ChromaDB<br/>collection: jarvis-conversations"]
    end
    EMBED["Ollama embeddings<br/>nomic-embed-text"] --> CHR
    EMBED --> CHR2
```

> The two ChromaDB collections live in the same `data/chroma` directory but are
> separate collections (different namespaces). Facts store `Memory` metadata;
> history stores `{user, assistant, timestamp}` metadata.

---

## 5. Memory Data Contract

The stable `Memory` dataclass (`app/memory/schema.py`). This schema is a
protected contract — downstream code depends on these fields.

```mermaid
classDiagram
    class Memory {
        +str category
        +str memory_type
        +str value
        +str behavior
        +str id
        +float created_at
        +float updated_at
        +float last_used
        +str source
        +float confidence
        +float importance
        +int access_count
        +dict metadata
        +to_dict()
        +from_dict(data)
        +touch()
        +mark_updated()
        +format_for_prompt()
    }
    class MemoryResult {
        +Memory memory
        +float score
    }
    MemoryResult --> Memory
```

**Behavior constants:** `append` · `replace` · `ignore` · `delete`
**Source constants:** `user` · `system` · `inferred`
**Importance constants:** `low (0.3)` · `medium (0.5)` · `high (0.7)` · `critical (0.9)`
