# JARVIS — Startup & Initialization Flow

> Traced from `app/main.py::main()`. The orchestrator constructs every subsystem
> once, then enters the REPL loop. Component construction order matters because
> some subsystems depend on others at init time (e.g. the retriever is seeded
> from the loaded memory store).

---

## 1. Initialization Sequence

```mermaid
sequenceDiagram
    participant OS as Process
    participant Main as main()
    participant Cfg as get_settings()
    participant MM as MemoryManager
    participant CM as ConversationManager
    participant PB as PromptBuilder
    participant CWM as ContextWindowManager
    participant SW as ModelSwitcher
    participant DA as DocumentationAgent

    OS->>Main: python app/main.py
    Main->>Cfg: load_dotenv() + get_settings()
    Cfg-->>Main: Settings singleton
    Main->>MM: MemoryManager(retriever=HybridRetriever(Vector+Keyword))
    MM->>MM: MemoryStore loads data/memories.json
    MM->>MM: retriever.on_index_rebuilt(memories)
    Main->>CM: ConversationManager()  (loads default.json)
    Main->>PB: PromptBuilder(SYSTEM_PROMPT)
    Main->>CWM: ContextWindowManager(max_tokens, safety_margin, model_name)
    Main->>SW: ModelSwitcher(settings)
    SW->>SW: create_client() per model key (cached)
    SW->>SW: build ModelRouter per profile
    Main->>DA: DocumentationAgent(switcher.get_client(docs) or default)
    Main->>CM: conv_store = ConversationVectorStore()
    Main->>CM: if empty, index_history(conversation.get_all())
    Main->>Main: print banner + tokenizer/memory stats
    Main->>Main: while True: REPL
```

---

## 2. Component Construction Graph

Which subsystem is wired into which at startup.

```mermaid
flowchart TB
    SET["get_settings()<br/>thread-safe singleton"] --> ALL["all subsystems read Settings"]

    subgraph MEMINIT["Memory init"]
        HYB["HybridRetriever"] --> VEC["VectorRetriever(ChromaDB)"]
        HYB --> KW["KeywordRetriever"]
        MM["MemoryManager"] --> HYB
        MM --> STORE["MemoryStore(data/memories.json)"]
    end

    subgraph MODELINIT["Models init"]
        SW["ModelSwitcher"] --> CL["clients cache<br/>create_client() x N"]
        SW --> RT["ModelRouter per profile"]
    end

    subgraph PIPEINIT["Pipeline init"]
        CM["ConversationManager"] --> CVS["ConversationVectorStore(ChromaDB)"]
        PB["PromptBuilder(SYSTEM_PROMPT)"]
        CWM["ContextWindowManager"] --> TOK["get_token_counter(model)"]
    end

    subgraph AGENTINIT["Agent init"]
        DA["DocumentationAgent"] --> SW
        DA --> TREG["ToolRegistry(GIT+FILE)"]
        TREG --> TEXE["ToolExecutor(require_confirmation=True)"]
    end

    SET --> MEMINIT
    SET --> MODELINIT
    SET --> PIPEINIT
    SET --> AGENTINIT
```

---

## 3. CLI Command Dispatch

Once the loop is running, `main()` dispatches on the raw input string.

```mermaid
flowchart TD
    IN["input('You: ')"] --> EMPTY{"empty?"}
    EMPTY -->|"yes"| CONT["continue"]
    EMPTY -->|"no"| CMD{"command?"}

    CMD -->|"quit"| QUIT["_cleanup() + break"]
    CMD -->|"docs"| DOCS["run_interactive(doc_agent)"]
    CMD -->|"memories"| MEM["_show_memories()"]
    CMD -->|"help"| HELP["_show_help()"]
    CMD -->|"stats"| STATS["_show_stats()"]
    CMD -->|"model"| MODEL{"model subcommand"}
    CMD -->|"anything else"| PIPE["main chat pipeline"]

    MODEL -->|"list"| ML["switcher.list_profiles()"]
    MODEL -->|"<name>"| MS["switcher.switch(name)<br/>+ re-point doc_agent"]
    MODEL -->|"no arg"| MI["_interactive_model_select()"]

    QUIT --> EXIT["Goodbye"]
    DOCS --> LOOP["back to REPL"]
    MEM --> LOOP
    HELP --> LOOP
    STATS --> LOOP
    ML --> LOOP
    MS --> LOOP
    MI --> LOOP
    PIPE --> LOOP
```

> `Ctrl+C` / `Ctrl+D` (`KeyboardInterrupt` / `EOFError`) also trigger
> `_cleanup()` + goodbye. `_cleanup()` calls `memory.save_if_dirty()` and
> `conversation.save_if_dirty()`.

---

## Git history verification

Full git history for this file (commit|author|date|subject):

```
1cab1b1|Er Sajan PLG|2026-07-13 08:12:24 +0545|mermaid added in docs/architecture and mermaid dependencies
```

Notes: This log was generated from the repository history for `docs/architecture/startup-flow.md`.
