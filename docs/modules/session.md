# Session Manager

**Status**: ACTIVE
**Type**: reference
**Source**: `app/session/` at HEAD
**Last Updated**: 2026-11-01
**Reviewed**: 2026-11-01

---

## Overview

Manages conversation sessions, state persistence and checkpointing for the
execution pipeline.

## Architecture

```
session/
├── __init__.py          # exports SessionManager, SessionPersistence
├── manager.py (SessionManager)
│   ├── get_or_create_session(session_id="default")
│   ├── get_or_create_conversation(...)
│   ├── update_preferences / fork_session / archive_session / delete_session
├── persistence.py (SessionPersistence)
│   ├── save_session / load_session
│   ├── save_conversation / load_conversation
│   └── delete_session (PostgreSQL or filesystem)
├── checkpointer.py (Checkpointer Protocol, MemorySaverAdapter, LangGraphCheckpointer)
├── postgres_checkpointer.py (PostgresCheckpointer)
└── context.py (trim_conversation, estimate_tokens)
```

## Components

### SessionManager

In-memory session store backed by `SessionPersistence` (filesystem by
default, PostgreSQL when `JARVIS_POSTGRES_URL` is set).

### Checkpointing

- `MemorySaverAdapter` — in-memory `Checkpointer` implementation
- `LangGraphCheckpointer` — SQLite-backed (`data/checkpoints.db`)
- `PostgresCheckpointer` — PostgreSQL-backed

### Persistence

`SessionPersistence` writes sessions/conversations to `data/sessions/` or
PostgreSQL via asyncpg.

## Configuration

- `JARVIS_SESSION_STORAGE` — not read by this package; backend is selected by
  whether `JARVIS_POSTGRES_URL` is set.
- `JARVIS_POSTGRES_URL` — PostgreSQL connection string (optional)

## API

```python
from app.session import SessionManager

manager = SessionManager()
session = await manager.get_or_create_session("default")
```
