# Session Manager

**Status**: ACTIVE
**Type**: reference
**Source**: `app/session/` at HEAD
**Last Updated**: 2026-09-17

---

## Overview

Manages conversation sessions, state persistence, and checkpointing for the LangGraph execution pipeline.

## Architecture

```
session/
├── __init__.py
├── manager.py (SessionManager)
│   ├── create_session(user_id)
│   ├── get_session(session_id)
│   └── delete_session(session_id)
├── checkpointer.py (LangGraphCheckpoint)
│   ├── save_checkpoint(state)
│   └── load_checkpoint(session_id)
├── context.py (SessionContext)
├── persistence.py (PostgreSQL persistence)
│   ├── asyncpg_postgres_persistence()
│   └── jsonb_table()
└── postgres_checkpointer.py (PostgresCheckpointer)
```

## Components

### SessionManager

In-memory session store with:
- User-to-session mapping
- Session metadata (created_at, updated_at, metadata dict)
- Message history buffer (last 100 messages)

### LangGraphCheckpoint

Checkpointing for LangGraph workflows:
- Saves execution state at each step
- Enables pause/resume for HITL workflows
- Storage: filesystem (default) or PostgreSQL

### Persistence

PostgreSQL-backed session persistence:
- JSONB columns for flexible schema
- Async I/O via `asyncpg`
- Connection pooling

## Configuration

- `JARVIS_SESSION_STORAGE`: Storage backend (`memory` or `postgres`)
- `JARVIS_POSTGRES_URL`: PostgreSQL connection string
- `JARVIS_SESSION_TTL`: Session TTL in seconds (default: 3600)

## API

```python
from app.session import SessionManager

manager = SessionManager()
session = await manager.create_session(user_id="user-123")
state = await manager.get_session(session.session_id)
```
