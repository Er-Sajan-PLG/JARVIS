# JARVIS Memory System

This document outlines the architecture, lifecycle, and components of the JARVIS memory system, focusing on how information is stored, retrieved, and utilized.

## 1. Memory Architecture

The JARVIS memory system is designed with a layered architecture to separate concerns, improve maintainability, and allow for flexible component swapping.

-   **`MemoryManager`**: The primary interface for external modules to interact with the memory system. It orchestrates the entire memory lifecycle, including storing, retrieving, updating, and deleting memories. It applies behavior rules (append, replace, ignore, delete) and coordinates between the `MemoryStore`, `CandidateRetriever`, and `MemoryRanker`.
-   **`MemoryStore`**: A low-level component responsible for CRUD (Create, Read, Update, Delete) operations and persistence of `Memory` objects. It handles saving memories to and loading them from disk (JSON format) and tracks unsaved changes. It has no business logic regarding retrieval or ranking.
-   **`CandidateRetriever` (Protocol)**: Defines the interface for retrieving potential candidate memories.
    -   **`KeywordRetriever`**: An implementation of `CandidateRetriever` that uses keyword overlap between a query and memories to find candidates. It extracts keywords, removes stop words, and checks for a minimum keyword overlap.
    -   **`VectorRetriever`**: An implementation of `CandidateRetriever` that uses semantic search via vector embeddings. It leverages ChromaDB and OllamaEmbeddingFunction to store memory embeddings and query them for similarity.
    -   **`HybridRetriever`**: Combines `KeywordRetriever` and `VectorRetriever` by running them in parallel, deduplicating results by memory ID, and passing the union of candidates to the `MemoryRanker`. This ensures both exact and semantic matches are considered.
-   **`MemoryRanker`**: Ranks candidate memories (provided by a `CandidateRetriever`) based on multiple factors, producing `MemoryResult` objects with a relevance score. It allows for tuning of various ranking weights.
-   **`FactExtractor`**: A rule-based component responsible for extracting structured "facts" from raw user messages. It uses predefined `RULES` to identify categories, types, and values from sentences.
-   **`ConversationVectorStore`**: A separate vector store specifically for indexing and retrieving past conversation exchanges. It stores raw user-assistant message pairs, allowing JARVIS to find semantically similar past dialogues.

## 2. Memory Lifecycle

### Creation (Storing)

1.  **Fact Extraction**: User messages are first processed by `FactExtractor` (if applicable) to identify structured facts (e.g., "my name is Sajan"). These facts are represented as dictionaries with `category`, `type`, `value`, and a `behavior` (append, replace, ignore, delete).
2.  **`MemoryManager.store()`**: This is the primary entry point for storing new memories.
    *   It checks the `behavior` field of the incoming fact.
    *   `BEHAVIOR_IGNORE`: The fact is discarded.
    *   `BEHAVIOR_DELETE`: Calls `delete_by_type()` to remove existing memories matching the category and type.
    *   `BEHAVIOR_REPLACE`: Calls `_handle_replace()`. If an existing memory matches the `category` and `type`, its `value`, `source`, and `updated_at` timestamp are updated. If no match, it falls back to `_handle_append()`.
    *   `BEHAVIOR_APPEND`: Calls `_handle_append()`. A new `Memory` object is created with a unique ID, timestamps (`created_at`, `updated_at`, `last_used`), source, confidence, and importance.
3.  **`MemoryStore.add()`**: The newly created or updated `Memory` object is added to the internal list of memories within `MemoryStore`.
4.  **Retriever Indexing**: The `CandidateRetriever` (or its components, `KeywordRetriever` and `VectorRetriever`) is notified via `on_memory_added()`.
    *   `KeywordRetriever` adds the memory to its internal list.
    *   `VectorRetriever` upserts the memory into its ChromaDB collection, creating an embedding for the memory's text (`category type: value`).
5.  **Persistence**: `MemoryStore.save()` or `MemoryStore.save_if_dirty()` is called to persist the changes to the `memories.json` file.

### Retrieval

1.  **`MemoryManager.retrieve()`**: This method takes a `prompt` and a `limit`.
2.  **Candidate Generation**: `MemoryManager` delegates to the `CandidateRetriever` (typically `HybridRetriever`) to find an overshot list of potential memories.
    *   `HybridRetriever` runs both `KeywordRetriever.find_candidates()` and `VectorRetriever.find_candidates()` in parallel.
        *   `KeywordRetriever` identifies memories with keyword overlap with the `prompt`.
        *   `VectorRetriever` performs a semantic search against its ChromaDB collection using an embedding of the `prompt`.
    *   `HybridRetriever` then deduplicates the results by memory ID and returns a combined list of `Memory` objects.
3.  **Ranking**: The candidate `Memory` objects are passed to the `MemoryRanker.rank()`.
    *   `MemoryRanker` calculates individual scores for each memory based on:
        *   **Relevance**: Keyword overlap with the query (`_score_relevance()`).
        *   **Importance**: The memory's `importance` attribute (`_score_importance()`).
        *   **Frequency**: Normalized `access_count` (`_score_frequency()`).
        *   **Recency**: Time since `last_used` with exponential decay (`_score_recency()`).
        *   **Confidence**: The memory's `confidence` attribute (`_score_confidence()`).
    *   These individual scores are combined using configurable `RankingWeights`.
    *   Memories below a `min_relevance_score` are filtered out.
    *   The remaining `MemoryResult` objects (memory + score) are sorted by score in descending order and trimmed to the specified `limit`.
4.  **Access Statistics Update**: For each `Memory` in the final ranked results, `memory.touch()` is called, which updates its `last_used` timestamp and increments its `access_count`.
5.  **Persistence**: `MemoryStore.force_save()` is called to persist the updated access statistics.

### Update

1.  **`MemoryManager.update()`**: Takes a `memory_id` and a dictionary of `updates`.
2.  **`MemoryStore.update_fields()`**: Locates the memory by ID and updates the specified fields using `setattr()`.
3.  **Timestamp Update**: The `memory.mark_updated()` method is called, setting `updated_at` to the current time.
4.  **Callbacks**: If an `_on_update` callback is registered, it is invoked.
5.  **Persistence**: `MemoryStore.save_if_dirty()` persists the changes. The retriever is not explicitly notified on general updates, but for updates to `value`, `category`, or `type` which affect embeddings, a full `on_index_rebuilt` might be necessary or re-upserting the single memory (which `VectorRetriever.on_memory_added` does).

### Deletion

1.  **`MemoryManager.delete()` / `MemoryManager.delete_by_type()`**: Removes memories by ID or by `category` and `type`.
2.  **`MemoryStore.remove()` / `MemoryStore.remove_by_category_and_type()`**: Removes the specified memories from the internal list.
3.  **Retriever Notification**: The `CandidateRetriever` (or its components) is notified via `on_memory_removed()` for each deleted memory.
    *   `KeywordRetriever` removes the memory from its internal list.
    *   `VectorRetriever` deletes the corresponding entry from its ChromaDB collection.
4.  **Callbacks**: If an `_on_delete` callback is registered, it is invoked for each removed memory.
5.  **Persistence**: `MemoryStore.save()` persists the changes.

## 3. Storage Formats

### `Memory` Dataclass (`app/memory/schema.py`)

All core memories are represented by the `Memory` dataclass, which includes rich metadata:

-   `id`: Unique identifier (8-character UUID prefix).
-   `category`: Broad classification (e.g., "identity", "preference", "skill").
-   `memory_type`: Specific type within a category (e.g., "name", "like", "ability").
-   `value`: The actual content of the memory (string).
-   `behavior`: How to handle new memories of this type ("append", "replace", "ignore", "delete").
-   `created_at`: Timestamp of creation (immutable).
-   `updated_at`: Timestamp of last modification (mutable).
-   `last_used`: Timestamp of last retrieval (mutable, used for ranking).
-   `source`: Origin of the memory ("user", "system", "inferred").
-   `confidence`: Reliability score (0.0 to 1.0).
-   `importance`: Significance score (0.0 to 1.0).
-   `access_count`: How many times the memory has been retrieved.
-   `metadata`: An open-ended dictionary for additional data.

Memories are serialized to and deserialized from dictionaries (`to_dict()`, `from_dict()`) for JSON storage and ChromaDB metadata.

### `MemoryStore` Persistence (`app/memory/store.py`)

The `MemoryStore` persists memories to a JSON file (default `data/memories.json`). The format is a dictionary containing a `version` ("2.0") and a list of memories, where each memory is the dictionary representation of the `Memory` dataclass.

```json
{
  "version": "2.0",
  "memories": [
    {
      "id": "abc12345",
      "category": "identity",
      "type": "name",
      "value": "Sajan",
      "behavior": "append",
      "created_at": 1678886400.0,
      "updated_at": 1678886400.0,
      "last_used": 1678886400.0,
      "source": "user",
      "confidence": 1.0,
      "importance": 0.5,
      "access_count": 1,
      "metadata": {}
    }
  ]
}
```

It also handles loading older "v1" formats for backward compatibility.

### `VectorRetriever` and `ConversationVectorStore` Persistence

Both `VectorRetriever` and `ConversationVectorStore` use `chromadb.PersistentClient` with `path="data/chroma"`.

-   **`VectorRetriever`**: Stores memories in a collection named "jarvis-memories".
    -   `ids`: `memory.id`
    -   `documents`: A textual representation of the memory for embedding: `f"{memory.category} {memory.memory_type}: {memory.value}"`.
    -   `metadatas`: The dictionary representation of the `Memory` object, allowing full reconstruction.
-   **`ConversationVectorStore`**: Stores conversation exchanges in a collection named "jarvis-conversations".
    -   `ids`: A hashed ID generated from timestamp and user message.
    -   `documents`: A combined user and assistant message: `f"User: {user_msg}\nAssistant: {assistant_msg}"`. This is what gets embedded.
    -   `metadatas`: A dictionary containing `user`, `assistant` (truncated to 1000 chars), and `timestamp`.

## 4. Retrieval Pipeline

The retrieval pipeline is orchestrated by `MemoryManager.retrieve()` and primarily driven by the `HybridRetriever`.

1.  **Query Input**: A `prompt` (user query) is received by `MemoryManager.retrieve()`.
2.  **Candidate Generation**: `HybridRetriever.find_candidates()` is called with the `prompt`.
    *   It internally calls `KeywordRetriever.find_candidates(prompt)` and `VectorRetriever.find_candidates(prompt)` in parallel.
    *   `KeywordRetriever` tokenizes the `prompt` into keywords (removing stop words) and compares them against keywords extracted from all stored memories (`memory.value`, `memory.category`, `memory.memory_type`). It returns memories with a minimum keyword overlap.
    *   `VectorRetriever` uses the `OllamaEmbeddingFunction` to embed the `prompt` and performs a cosine similarity search in its ChromaDB collection ("jarvis-memories") to find semantically similar memory embeddings. It then reconstructs `Memory` objects from the retrieved metadata.
    *   `HybridRetriever` merges these two lists of candidate `Memory` objects, deduplicating by `memory.id`. It returns an overshot list (e.g., 3x the final `limit`) to provide `MemoryRanker` with more options.
3.  **Ranking**: The combined candidate memories are passed to `MemoryRanker.rank()` along with the original `prompt`. This step is detailed in section 5.
4.  **Result Filtering and Sorting**: `MemoryRanker` scores and sorts the candidates, filtering out those below a `min_relevance_score` and returning the top `limit` `MemoryResult` objects.
5.  **Access Update**: `MemoryManager` iterates through the final `MemoryResult`s, calls `memory.touch()` on each `Memory` to update its `last_used` timestamp and increment `access_count`, and then triggers a `MemoryStore.force_save()`.

## 5. Ranking

The `MemoryRanker` is responsible for assigning a relevance score to candidate memories. It uses a weighted combination of several factors:

-   **`RankingWeights`**: A dataclass (`app/memory/ranking.py`) that defines the importance of each factor. Default weights are:
    -   `relevance`: 0.35 (keyword/vector overlap with query)
    -   `importance`: 0.25 (manually set or inferred importance of the memory)
    -   `frequency`: 0.15 (how often the memory has been accessed, log scale)
    -   `recency`: 0.15 (time since the memory was last used, exponential decay with a half-life)
    -   `confidence`: 0.10 (reliability of the fact)

### Scoring Factors:

-   **Relevance (`_score_relevance`)**:
    -   Calculates a Jaccard-like similarity based on keyword overlap between the query and the memory's `value`, `category`, and `memory_type`.
    -   Applies a boost if the memory's `category` or `memory_type` are present as keywords in the query.
-   **Importance (`_score_importance`)**: Directly uses the `memory.importance` attribute (0.0 to 1.0).
-   **Frequency (`_score_frequency`)**:
    -   Uses a logarithmic scale on `memory.access_count`.
    -   Normalizes such that `access_count` equal to `frequency_scale` (default 10) results in a score of 1.0.
-   **Recency (`_score_recency`)**:
    -   Applies exponential decay based on `age_seconds = current_time - memory.last_used`.
    -   A `recency_half_life_days` (default 7.0 days) determines how quickly older memories' scores fade.
-   **Confidence (`_score_confidence`)**: Directly uses the `memory.confidence` attribute (0.0 to 1.0).

These individual scores are multiplied by their respective weights and summed to produce a total score for each `MemoryResult`.

## 6. Fact Extraction

`FactExtractor` (`app/memory/fact_extractor.py`) is a rule-based system designed to identify and extract structured information ("facts") from raw text, typically user messages.

1.  **Sentence Splitting**: The input `message` is first split into individual sentences using `_split_into_sentences()`, which attempts to handle common abbreviations to prevent incorrect splitting.
2.  **Rule Matching**: Each sentence is iterated through, and its lowercase version is checked against a predefined set of `RULES` (`app/memory/rules.py`).
3.  **Triggers**: Each `rule` has a list of `triggers` (e.g., "i am ", "my name is "). If a trigger is found in the sentence, it's considered a potential match.
4.  **Value Extraction (`_extract_value`)**: If a trigger matches, the text immediately following the trigger is extracted as the `value`. This extraction stops at predefined `VALUE_BOUNDARIES` (e.g., coordinating conjunctions, subordinating conjunctions, sentence endings) to ensure only relevant information is captured. The value is then cleaned (trimmed, removes leading articles/prepositions).
5.  **Fact Creation**: If a valid `value` is extracted (length >= 2), a fact dictionary is created containing: `category`, `type`, `value`, `behavior` (from the rule), `source` (default "user"), and a `confidence` of 1.0.
6.  **Return**: A list of these fact dictionaries is returned, ready to be stored by `MemoryManager.store()`.

The rules define various categories like "identity", "preferences", "skills", "goals", "plans", "tasks", "location", and "profession", each with specific `type`s and a default `behavior`.

## 7. Vector Search

Vector search is implemented using ChromaDB and `OllamaEmbeddingFunction` for both `VectorRetriever` (for general memories) and `ConversationVectorStore` (for conversation history).

-   **`OllamaEmbeddingFunction`**: This function is initialized with the URL of an Ollama server (`http://localhost:11434`) and an embedding model (`nomic-embed-text`). It is responsible for converting text into numerical vector embeddings.
-   **`chromadb.PersistentClient`**: Initializes a client that persists data to disk in a specified directory (`data/chroma`).
-   **Collections**:
    -   `VectorRetriever` uses a collection named "jarvis-memories".
    -   `ConversationVectorStore` uses a collection named "jarvis-conversations".
    -   Both collections use "cosine" similarity for HNSW (Hierarchical Navigable Small World) indexing.

### How it works:

1.  **Embedding on Storage**:
    *   When a `Memory` is added to `VectorRetriever`, its textual representation (`f"{category} {type}: {value}"`) is embedded by `OllamaEmbeddingFunction`, and the resulting vector (along with `id` and `metadata`) is stored in ChromaDB.
    *   When a conversation exchange is added to `ConversationVectorStore`, the combined user and assistant messages (`f"User: {user_msg}\nAssistant: {assistant_msg}"`) are embedded and stored.
2.  **Embedding on Query**:
    *   When a `query` (e.g., user prompt) is submitted for retrieval or search, `OllamaEmbeddingFunction` embeds the query text.
3.  **Similarity Search**:
    *   ChromaDB performs a similarity search (using cosine similarity on the vector embeddings) to find documents (memories or conversation exchanges) whose embeddings are closest to the query embedding.
    *   The `n_results` parameter limits the number of results returned.
4.  **Result Retrieval**: The search returns the `ids`, `documents`, and `metadatas` of the most similar items. These metadatas are then used to reconstruct the original `Memory` objects or conversation dictionaries.

## 8. Conversation Memory

The `ConversationVectorStore` (`app/memory/conversation_store.py`) is a specialized vector store designed to remember past interactions semantically, distinct from the structured facts stored in `MemoryManager`.

-   **Purpose**: It allows JARVIS to recall previous conversations based on meaning, rather than just keywords, providing context and reducing repetition.
-   **Storage**:
    -   It creates a separate ChromaDB collection named "jarvis-conversations".
    -   It stores pairs of user and assistant messages. The `document` that gets embedded is `f"User: {user_msg}\nAssistant: {assistant_msg}"`.
    -   `metadata` includes the raw `user` and `assistant` messages (capped at 1000 characters) and a `timestamp`.
-   **Indexing**:
    -   `index_history()`: Used for bulk importing existing conversation history. It extracts user-assistant pairs from a list of messages.
    -   `add_exchange()`: Used to add a single new user-assistant exchange after it completes.
-   **Search**:
    -   `search(query, limit)`: Takes a `query`, embeds it, and finds semantically similar past conversation exchanges from the ChromaDB collection.
    -   Returns a list of dictionaries, each containing the `user` and `assistant` message of a retrieved exchange.

## 9. Future Improvements

Based on code comments and common patterns in memory systems, several areas are noted for potential future improvements:

-   **LLM-based Fact Extraction**: The `FactExtractor` is currently rule-based. The comment "Interface is stable - can swap to LLM extraction later" in `app/memory/fact_extractor.py` indicates a planned transition to more sophisticated LLM-driven fact extraction, which would likely be more flexible and comprehensive.
-   **Improved Retriever Updates**: While `VectorRetriever.on_index_rebuilt` makes N embedding calls on rebuild, the current system might not always optimally update vector embeddings when only a small part of a memory (like `value`) changes, potentially leading to stale embeddings until a full rebuild.
-   **More Sophisticated Merging**: The `MemoryManager.merge()` method currently concatenates new values with existing ones using a semicolon. A more intelligent merging strategy might involve LLM-based summarization or reconciliation of conflicting information.
-   **Adaptive Ranking Weights**: The `RankingWeights` are static. Future improvements could involve dynamic adjustment of these weights based on user feedback or observed retrieval performance.
-   **Proactive Memory Generation**: The current system primarily reacts to user input for memory creation. A proactive system could infer new memories or update existing ones based on observations, agent actions, or long-term trends.
-   **Forgetting Mechanisms**: While recency is a factor in ranking, explicit forgetting or consolidation mechanisms for less important or redundant memories could be explored to manage memory growth and focus on salient information.
-   **Memory of Interactions with Tools/Skills**: Extending the memory system to store details about how JARVIS uses tools or skills, which could inform future decision-making.
