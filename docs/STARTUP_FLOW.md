# Application Startup Flow for JARVIS v2.4.0

This document outlines the startup sequence of the JARVIS application, tracing execution from its entry point to the initiation of user request processing.

## 1. Entry Point

The application's execution begins in `app/main.py`.

-   **File**: `app/main.py`
-   **Execution Start**: The `if __name__ == "__main__":` block directly calls the `main()` function.

```python app/main.py
if __name__ == "__main__":
    main()
```

## 2. Startup Sequence and Initialization Order

The `main()` function orchestrates the initialization of various core components.

1.  **Environment Variables Loading**:
    *   `from dotenv import load_dotenv`
    *   `load_dotenv()`: Loads environment variables from a `.env` file, if present. This happens before any other application logic.

2.  **Version Display**:
    *   `from app.config.version import VERSION`
    *   Prints a banner with the JARVIS version (e.g., "JARVIS v.2.2.0").

3.  **Configuration Loading**:
    *   `settings = get_settings()`
    *   **Description**: The `get_settings()` function (from `app/config/settings.py`) is called. This function implements a thread-safe singleton pattern to ensure settings are loaded only once.
    *   **Process**:
        1.  It checks if a global `_settings` instance already exists. If not, it acquires a thread lock.
        2.  It then calls `Settings.load()`.
        3.  `Settings.load(path="config.yaml")` attempts to load configuration from `config.yaml`.
        4.  If `config.yaml` does not exist, default settings (defined as dataclass fields in `app/config/settings.py`) are used.
        5.  If `config.yaml` exists, it is parsed, and values from the YAML file override the default settings.
        6.  The loaded or default `Settings` object is stored in `_settings`.
    *   **Objects Created**: A `Settings` object, which is a dataclass containing nested configuration objects like `ModelConfig`, `MemoryConfig`, `ContextConfig`, `ConversationConfig`, `RetrievalConfig`, `RankingConfig`, and `PathsConfig`.

4.  **Subsystem Initialization**:

    *   **MemoryManager**:
        *   `memory = MemoryManager(...)`
        *   **Dependencies**: Requires a `retriever`.
        *   **Objects Created**:
            *   `MemoryManager` instance.
            *   `HybridRetriever` instance.
            *   `VectorRetriever` instance (with `persist_dir="data/chroma"` and `ollama_url="http://localhost:11434"`).
            *   `KeywordRetriever` instance (with `min_keyword_overlap=1`).

    *   **ConversationManager**:
        *   `conversation = ConversationManager()`
        *   **Dependencies**: None at initialization.
        *   **Objects Created**: `ConversationManager` instance.

    *   **PromptBuilder**:
        *   `prompt_builder = PromptBuilder(system_prompt=SYSTEM_PROMPT)`
        *   **Dependencies**: `SYSTEM_PROMPT` (imported from `app/config/prompt.py`).
        *   **Objects Created**: `PromptBuilder` instance.

    *   **ConversationVectorStore**:
        *   `conv_store = ConversationVectorStore(persist_dir="data/chroma")`
        *   **Dependencies**: None explicitly passed, but likely depends on an embedding model for vectorization (though this is abstracted within its implementation, not explicitly passed here).
        *   **Initialization Logic**: Checks `conv_store.count()`. If 0, it calls `conv_store.index_history(conversation.get_all())` to index existing conversation history.
        *   **Objects Created**: `ConversationVectorStore` instance.

    *   **ContextWindowManager**:
        *   `context_manager = ContextWindowManager(...)`
        *   **Dependencies**: `settings.context.max_tokens`, `settings.context.safety_margin`, `settings.default_model`.
        *   **Objects Created**: `ContextWindowManager` instance.

    *   **ModelSwitcher**:
        *   `switcher = ModelSwitcher(settings)`
        *   **Dependencies**: The `settings` object. Internally, this will create a `ModelRouter` and various model clients (e.g., `LlamaCppClient`, `OllamaClient`, `OpenRouterClient`) based on the `settings.models` configuration.
        *   **Objects Created**: `ModelSwitcher` instance, `ModelRouter` instance, and potentially multiple `ModelClient` instances (depending on configured models).

    *   **DocumentationAgent**:
        *   `doc_agent = DocumentationAgent(model=switcher.get_client(...))`
        *   **Dependencies**: A model client obtained from the `ModelSwitcher` based on the `settings.active_profile` and its "docs" key.
        *   **Objects Created**: `DocumentationAgent` instance.

5.  **Information Display**:
    *   Tokenizer information (`context_manager.get_tokenizer_info()`) is printed.
    *   Counts of loaded memories (`memory.count()`) and messages (`conversation.count()`) are displayed.
    *   A list of available commands is printed to the console.

## 3. Configuration Loading

Configuration is managed by the `app.config.settings` module.

-   **Primary Configuration File**: `config.yaml` (optional). If this file exists at the project root, it will override default settings.
-   **Default Configuration**: Defined within `app/config/settings.py` using dataclasses (`Settings`, `ModelConfig`, `MemoryConfig`, etc.).
-   **Loading Mechanism**: The `get_settings()` function provides a thread-safe singleton for accessing the application settings. It first attempts to load `config.yaml`. If not found, it proceeds with the hardcoded default values.
-   **Environment Variables**: `load_dotenv()` is called at the very beginning of `main.py` to load variables from a `.env` file, which can also influence configuration (e.g., API keys, URLs).

## 4. Dependency Graph (Key Initializations)

The following illustrates the primary dependencies during the startup phase:

```
main.py
├── .env (loaded by dotenv)
├── app/config/settings.py (get_settings())
│   └── config.yaml (optional, overrides defaults)
├── app/config/prompt.py (SYSTEM_PROMPT)
├── app/config/version.py (VERSION)
├── MemoryManager
│   └── HybridRetriever
│       ├── VectorRetriever
│       └── KeywordRetriever
├── ConversationManager
├── PromptBuilder (depends on SYSTEM_PROMPT)
├── ConversationVectorStore
├── ContextWindowManager (depends on settings)
├── ModelSwitcher (depends on settings)
│   └── ModelRouter (created internally, depends on settings.models)
│       └── Various ModelClient instances (e.g., LlamaCppClient)
└── DocumentationAgent (depends on ModelSwitcher for a model client)
```

## 5. Event Loop

After all initializations, the application enters its main interactive loop:

-   **Type**: An infinite `while True:` loop.
-   **User Interaction**: It continuously prompts the user for input using `input("You: ")`.
-   **Command Handling**: Special commands like `quit`, `docs`, `memories`, `help`, and `stats` are processed directly.
-   **Main Pipeline**: If the input is not a special command, it proceeds through the core JARVIS pipeline (adding message, extracting facts, storing, retrieving, building prompt, fitting context, generating response, and adding assistant's response).
-   **Error Handling**: A `try-except` block catches `EOFError` and `KeyboardInterrupt` to gracefully handle termination, as well as `Exception` during model generation.

## 6. Shutdown Sequence

The application handles shutdown gracefully when the user types "quit" or sends an EOF/KeyboardInterrupt signal.

-   **Trigger**: User input "quit" or `EOFError`/`KeyboardInterrupt` (e.g., Ctrl+D or Ctrl+C).
-   **Function Call**: The `_cleanup(memory, conversation)` helper function is invoked.
-   **Cleanup Actions**:
    *   `memory.save_if_dirty()`: Ensures any unsaved changes in the `MemoryManager` are persisted (e.g., to `data/memories.json`).
    *   `conversation.save_if_dirty()`: Ensures any unsaved changes in the `ConversationManager` are persisted (e.g., to `data/conversations/default.json`).
-   **Exit**: The `break` statement exits the `while True:` loop, ending the `main()` function and thus the program.
