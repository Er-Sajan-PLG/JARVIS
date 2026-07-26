# JARVIS Architecture Document

## Purpose

This document provides a comprehensive overview of JARVIS's architecture, designed primarily to help new developers understand the system's structure, components, and operational flow. It details the high-level design, startup sequence, inter-component dependencies, and underlying design principles, ensuring maintainability, extensibility, and clarity for future development.

## High-Level Architecture

JARVIS operates as a modular AI assistant, primarily driven by a conversational loop. Its core functionality revolves around processing user input, retrieving relevant information from various memory systems, constructing informed prompts for Language Models (LLMs), generating responses, and updating its internal state. The system is designed with a clear separation of concerns, allowing individual components to be developed, tested, and maintained independently.

Key architectural principles:
*   **Modularity:** Components are self-contained with well-defined interfaces.
*   **Extensibility:** New models, tools, and memory types can be added with minimal disruption.
*   **Configurability:** Behavior is driven by a centralized `settings.py` and `config.yaml`.
*   **Memory-centric:** The system heavily relies on persistent memory and contextual retrieval to inform responses.

## Layer Diagram

```mermaid
graph TD
    User --> MainLoop
    MainLoop --> ConversationManager
    MainLoop --> FactExtractor
    MainLoop --> MemoryManager
    MainLoop --> PromptBuilder
    MainLoop --> ContextWindowManager
    MainLoop --> ModelSwitcher
    MainLoop --> DocumentationAgent

    ConversationManager --> MemoryManager
    ConversationManager --> ConversationVectorStore

    FactExtractor --> MemoryManager
    FactExtractor --> MemoryRules

    MemoryManager --> MemoryStore
    MemoryManager --> HybridRetriever
    MemoryManager --> MemoryRanker

    HybridRetriever --> KeywordRetriever
    HybridRetriever --> VectorRetriever

    VectorRetriever --> ChromaDB
    VectorRetriever --> OllamaEmbeddingFunction

    MemoryRanker --> MemorySchema

    PromptBuilder --> SystemPrompt
    PromptBuilder --> MemorySchema
    PromptBuilder --> ConversationManager(get_recent_formatted)
    PromptBuilder --> ConversationVectorStore(search)

    ContextWindowManager --> Tokenizer

    ModelSwitcher --> Settings
    ModelSwitcher --> ModelFactory
    ModelSwitcher --> ModelRouter

    ModelFactory --> LlamaCppClient
    ModelFactory --> OllamaClient
    ModelFactory --> OpenRouterClient

    ModelRouter --> TaskTypeEnum
    ModelRouter --> ModelClient(Abstract)

    DocumentationAgent --> ModelClient
    DocumentationAgent --> ToolRegistry
    DocumentationAgent --> ToolExecutor

    ToolExecutor --> ToolRegistry
    ToolRegistry --> GitTools
    ToolRegistry --> FileTools

    subgraph app
        subgraph Agents
            DocumentationAgent
        end
        subgraph API
            % Empty for now
        end
        subgraph Brain
            % Empty for now
        end
        subgraph Config
            Settings
            SystemPrompt
            MemoryRules
        end
        subgraph Context
            ContextWindowManager
        end
        subgraph Conversation
            ConversationManager
            ConversationVectorStore
        end
        subgraph Memory
            MemoryManager
            FactExtractor
            MemoryStore
            HybridRetriever
            KeywordRetriever
            VectorRetriever
            MemoryRanker
            MemorySchema
        end
        subgraph Models
            ModelSwitcher
            ModelFactory
            ModelRouter
            LlamaCppClient
            OllamaClient
            OpenRouterClient
            ModelClient(Abstract)
            TaskTypeEnum
        end
        subgraph Prompt
            PromptBuilder
        end
        subgraph Tools
            ToolRegistry
            ToolExecutor
            GitTools
            FileTools
        end
        subgraph Utils
            Tokenizer
        end
    end

    subgraph Data
        ChromaDB
    end

    subgraph External
        OllamaEmbeddingFunction
        LlamaCppServer
        OllamaServer
        OpenRouterAPI
    end

    MainLoop --> Settings

---

## Git history verification

Full git history for this file (commit|author|date|subject):

```
6ea9796|Er Sajan PLG|2026-07-11 22:42:47 +0545|feat(platform): expand model backends and configuration system
```

Notes: This log was generated from the repository history for `docs/ARCHITECTURE_CONTINUE_AGENT.md`.
```

## Startup Flow

The application's startup flow is orchestrated by `app/main.py`.

1.  **Environment Loading:** `dotenv.load_dotenv()` is called to load environment variables from `.env` files.
2.  **Settings Initialization:** `app.config.settings.get_settings()` is called. This function is a thread-safe singleton that:
    *   Loads `config.yaml` if it exists.
    *   Initializes a `Settings` dataclass with default values, overriding them with values from `config.yaml` if present.
3.  **Subsystem Initialization:** In the `main()` function, various managers and builders are instantiated:
    *   **MemoryManager:**
        *   Instantiated with a `HybridRetriever`.
        *   `HybridRetriever` itself is instantiated with a `VectorRetriever` (using ChromaDB and OllamaEmbeddingFunction) and a `KeywordRetriever`.
        *   The `MemoryStore` is initialized internally by `MemoryManager`, loading `data/memories.json`.
        *   The `HybridRetriever`'s internal keyword and vector indexes are rebuilt from the loaded memories.
        *   A `MemoryRanker` is also initialized within `MemoryManager`.
    *   **ConversationManager:**
        *   Loads conversation history from `data/conversations/default.json`.
    *   **PromptBuilder:**
        *   Initialized with `app.config.prompt.SYSTEM_PROMPT`.
    *   **ConversationVectorStore:**
        *   Initializes another ChromaDB collection (`jarvis-conversations`) for embedding conversation exchanges.
        *   If the store is empty, it indexes existing conversation history from the `ConversationManager`.
    *   **ContextWindowManager:**
        *   Configured with `max_tokens`, `safety_margin` from settings, and the `default_model` name to select the appropriate tokenizer.
        *   Internally uses `app.utils.tokenizer.get_token_counter`.
    *   **ModelSwitcher:**
        *   Instantiated with the global `settings`.
        *   Pre-builds `ModelClient` instances for all defined models in `settings.models` (e.g., `LlamaCppClient`, `OllamaClient`, `OpenRouterClient`) using `app.models.factory.create_client`.
        *   Builds `ModelRouter` instances for each profile defined in `settings.profiles`, associating `TaskType`s (e.g., `GENERAL`, `CODE`, `DOCS`) with specific `ModelClient`s.
    *   **DocumentationAgent:**
        *   Instantiated with an `ModelClient` obtained from the `ModelSwitcher` based on the active profile's "docs" model.
        *   Internally initializes a `ToolRegistry` and `ToolExecutor` with `GIT_TOOLS` and `FILE_TOOLS`.

4.  **Status Output:** Initial system information (tokenizer, memory count, message count, commands) is printed to the console.
5.  **Main Event Loop:** The `while True` loop starts, awaiting user input.

## Dependency Injection

JARVIS employs a form of explicit dependency injection, primarily through constructor injection. This is evident in:
*   `MemoryManager` receiving `retriever` and `ranker` instances.
*   `HybridRetriever` receiving `KeywordRetriever` and `VectorRetriever`.
*   `DocumentationAgent` receiving a `ModelClient` instance.
*   `ToolExecutor` receiving a `ToolRegistry`.

This approach enhances modularity, testability, and allows for easy swapping of implementations (e.g., changing retrieval strategies or LLM backends) without altering the core logic of the consuming components.

## Component Responsibilities

*   **`app/main.py`**: The application's entry point; orchestrates the initialization of all major components and manages the main conversational loop.
*   **`app/config/settings.py`**: Centralized configuration management, loading from `config.yaml` and providing a singleton `Settings` object.
*   **`app/config/prompt.py`**: Defines the static `SYSTEM_PROMPT` that sets the AI's persona and core instructions.
*   **`app/config/version.py`**: Stores the current application version.
*   **`app/memory/manager.py`**: High-level orchestration of memory operations (store, retrieve, update, delete). Delegates to `MemoryStore`, `CandidateRetriever` (via `HybridRetriever`), and `MemoryRanker`.
*   **`app/memory/store.py`**: Low-level CRUD operations and persistence for `Memory` objects, saving to `data/memories.json`.
*   **`app/memory/fact_extractor.py`**: Extracts structured facts from natural language user input using rule-based patterns defined in `app/memory/rules.py`.
*   **`app/memory/retrieval.py` (`KeywordRetriever`)**: Retrieves memory candidates based on keyword overlap.
*   **`app/memory/vector_retriever.py`**: Retrieves memory candidates using semantic similarity via ChromaDB and Ollama embeddings.
*   **`app/memory/hybrid_retriever.py`**: Combines results from `KeywordRetriever` and `VectorRetriever`, deduplicates, and provides candidate memories.
*   **`app/memory/ranking.py` (`MemoryRanker`)**: Scores and sorts candidate memories based on multiple factors (relevance, importance, frequency, recency, confidence) to return the most relevant set.
*   **`app/memory/conversation_store.py`**: Stores and retrieves past conversation exchanges using vector embeddings (ChromaDB) for semantic search.
*   **`app/conversation/manager.py`**: Manages the chronological conversation history, adding new messages, retrieving recent exchanges, and persisting to `data/conversations/default.json`.
*   **`app/prompt/builder.py`**: Assembles the complete prompt for the LLM, combining the system prompt, relevant memories, past conversation exchanges, and the current user input into a structured list of messages.
*   **`app/context/manager.py`**: Manages the LLM's context window, ensuring the message history fits within the model's token limits by trimming older conversation pairs while preserving coherence.
*   **`app/models/factory.py`**: A factory for creating `ModelClient` instances based on their backend type (e.g., `llamacpp`, `ollama`, `openrouter`).
*   **`app/models/client.py`**: Abstract base class (Protocol) for all LLM clients, defining the `generate` interface.
*   **`app/models/llamacpp_client.py`**: Concrete implementation of `ModelClient` for interacting with `llama.cpp` compatible OpenAI-like API servers.
*   **`app/models/ollama_client.py`**: (Conditional) Implementation for Ollama models.
*   **`app/models/openrouter_client.py`**: (Conditional) Implementation for OpenRouter API.
*   **`app/models/router.py`**: Determines the appropriate `ModelClient` to use for a given prompt based on task classification (e.g., code, reasoning, general).
*   **`app/models/switcher.py`**: Manages multiple LLM profiles (e.g., "local", "cloud") and allows runtime switching between them. Builds and maintains a `ModelRouter` for the active profile.
*   **`app/utils/tokenizer.py`**: Provides token counting functionality, attempting to use `tiktoken`, `transformers`, or falling back to a word-based estimation.
*   **`app/utils/server_manager.py`**: Utility to check if a server is running on a given port and, if not, to start it in the background. (Currently commented out in `main.py`).
*   **`app/agents/doc_agent.py` (`DocumentationAgent`)**: A specialized agent that uses a mini-agentic loop and tool calling (`git_tools`, `file_tools`) to generate and update documentation (CHANGELOG, DEVLOG).
*   **`app/tools/base.py`**: Defines base classes for tools (`ToolResult`, `ToolDefinition`) and the `ToolRegistry`.
*   **`app/tools/executor.py`**: Parses tool calls from model output, executes them, handles user confirmation for risky tools, and formats results for re-injection into the prompt.
*   **`app/tools/git_tools.py`**: Provides Git-related tools (e.g., `git_log`, `git_diff_full`) for agents.
*   **`app/tools/file_tools.py`**: Provides file system tools (e.g., `read_file`, `append_file`) for agents, with an allowlist for security.

## Runtime Lifecycle (Main Loop)

The `main()` function contains the core `while True` loop that drives JARVIS's interaction:

1.  **User Input:** Prompts the user for input (`You: `).
2.  **Command Handling:** Checks for special commands like `quit`, `memories`, `help`, `stats`, and `model`.
    *   The `model` command interacts with the `ModelSwitcher` to change the active LLM profile.
    *   The `docs` command invokes the `DocumentationAgent` in an interactive mode.
3.  **Conversation Update:** Adds the user's prompt to the `ConversationManager`.
4.  **Fact Extraction:** Calls `extract_facts()` from `FactExtractor` on the user's prompt.
5.  **Fact Storage:** Iterates through extracted facts and stores them in the `MemoryManager`.
6.  **Memory Retrieval:** Retrieves relevant memories from `MemoryManager` based on the user's prompt.
7.  **Past Exchange Retrieval:** Searches `ConversationVectorStore` for semantically similar past conversation exchanges.
8.  **Prompt Building:** `PromptBuilder` constructs the final list of messages for the LLM, incorporating the `SYSTEM_PROMPT`, relevant memories, past exchanges, and the current conversation.
9.  **Context Window Fitting:** `ContextWindowManager` ensures the prompt fits within the LLM's `max_tokens` by trimming older message pairs if necessary.
10. **Model Routing:** `ModelSwitcher.router.route()` selects the appropriate `ModelClient` based on the user's prompt (e.g., a "code" model for programming questions).
11. **Response Generation (Streaming):** The selected `ModelClient.generate()` method is called to produce a response. This typically happens with streaming enabled, where `on_token` callback prints tokens as they arrive.
12. **Conversation Update:** The generated assistant response is added to the `ConversationManager`.
13. **Conversation Vector Store Update:** The user-assistant exchange is added to the `ConversationVectorStore` for future semantic retrieval.
14. **Context Stats:** If message trimming occurred, statistics are printed.
15. **Loop Continuation:** The loop repeats, awaiting the next user input.
16. **Cleanup:** Upon `quit` or `EOFError`/`KeyboardInterrupt`, `_cleanup()` is called to save any unsaved changes in `MemoryManager` and `ConversationManager`.

## Design Rationale

*   **Separation of Concerns:** Each major component (Memory, Conversation, Models, Context, Prompt) has a distinct responsibility, reducing coupling and improving maintainability. For example, `MemoryStore` handles persistence, while `MemoryManager` handles business logic and coordination.
*   **Pluggable Components:** The use of abstract interfaces (like `ModelClient` and `CandidateRetriever` Protocol) and dependency injection allows easy swapping of underlying implementations without affecting higher-level logic. This is crucial for supporting various LLM backends (LlamaCpp, Ollama, OpenRouter) and retrieval strategies.
*   **Memory-First Architecture:** Facts are extracted and stored *before* retrieval in the main loop. This ensures that new information provided by the user in the current turn is immediately available for context in the same turn's response.
*   **Hybrid Retrieval:** Combining keyword and vector-based retrieval (`HybridRetriever`) leverages the strengths of both, providing robust access to both exact factual matches and semantically similar information.
*   **Context Window Management:** Trimming conversation in user/assistant pairs, rather than individual messages, preserves conversational coherence and makes responses more natural, even under token constraints.
*   **Prompt-Based Tool Calling:** While the system is designed for future native function calling (v3.0), the current prompt-based tool calling mechanism in `DocumentationAgent` provides a robust and model-agnostic way for agents to interact with external tools, relying on the LLM's ability to follow instructions.
*   **Centralized Configuration:** All key parameters are managed through `app/config/settings.py` and `config.yaml`, making the system easy to configure and adapt without code changes.

## Future Improvements

*   **Native Function Calling (v3.0):** Transition the `ToolExecutor` to leverage native function calling capabilities of LLMs when available, simplifying parsing and improving reliability.
*   **More Advanced Fact Extraction:** Explore LLM-based fact extraction for improved accuracy and flexibility beyond rule-based triggers.
*   **Conversation Summarization:** Implement the `ConversationConfig.enable_summarization` feature to generate and use summaries for very long conversations, further optimizing context window usage.
*   **Dynamic Tool Discovery:** Implement a mechanism for tools to be dynamically discovered and registered at runtime, rather than being explicitly listed.
*   **Agent Orchestration Layer:** Introduce a higher-level agent orchestration layer (e.g., for multi-agent workflows or more complex reasoning chains).
*   **Modular Memory Backends:** Abstract `MemoryStore` further to easily integrate different persistent storage solutions beyond JSON files (e.g., databases).
*   **Enhanced Error Handling & Recovery:** Implement more sophisticated error handling and recovery mechanisms, especially around LLM API calls and tool executions.
*   **User Management & Multi-tenancy:** If expanded beyond a single-user CLI, introduce user authentication, authorization, and data isolation.

## Uncertainties / Unimplemented

*   **`app/api/` folder:** Currently empty. Its intended purpose (e.g., REST API endpoints) is inferred but not implemented.
*   **`app/brain/` folder:** Currently empty, suggesting it's a placeholder for future "brain" or reasoning modules. The `MemoryManager` and `ModelRouter` implicitly perform some "brain" functions.
*   **`app/memory/rules.py` limitations:** The fact extraction relies solely on string triggers. This can be brittle and limited; more advanced NLP techniques or LLM-based extraction would improve robustness.
*   **`app/utils/server_manager.py` usage:** While present, the code for `ensure_server_running` is commented out in `main.py`, meaning auto-starting LLM servers is currently disabled.
*   **`app/models/ollama_client.py` and `app/models/openrouter_client.py`:** These clients are conditionally imported based on `try-except` blocks, indicating they might rely on external Python packages that are not guaranteed to be installed. Their full functionality and integration depend on the presence of these packages.
*   **`app/tools/dev_logger.py` and `app/tools/project_scanner.py`:** These files exist in `app/tools/__pycache__` but not in the `app/tools` directory itself. This implies they might have been removed or are remnants of prior development and are not actively used or registered in `ToolRegistry`. Thus, their purpose and functionality are uncertain without source code.
