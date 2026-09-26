# app/session

<!-- generated:module_readmes begin -->

| Module | Purpose | Top-level API |
|---|---|---|
| `__init__.py` | JARVIS Session & Persistence Package. | — |
| `checkpointer.py` | LangGraph Checkpointing for JARVIS. | `Checkpoint`, `Checkpointer`, `LangGraphCheckpointer`, `MemorySaverAdapter`, `get_checkpointer()`, `get_postgres_checkpointer()` |
| `context.py` | Token-aware context-window management (Sprint 3 contract §6). | `TrimResult`, `estimate_tokens()`, `trim_conversation()` |
| `manager.py` | Live Session Manager. | `SessionManager` |
| `persistence.py` | Session & Execution Plan State Persistence Engine. | `SessionPersistence` |
| `postgres_checkpointer.py` | PostgreSQL-backed checkpointer for JARVIS. | `PostgresCheckpointer`, `_try_import_psycopg()` |

<!-- generated:module_readmes end -->
