# Context Builder

**Status**: ACTIVE
**Type**: reference
**Source**: `app/context/` at HEAD
**Last Updated**: 2026-09-17

---

## Overview

Builds and manages context for LLM conversations — retrieves relevant memories, session history, and system prompts to include in each model call.

## Architecture

```
context/
├── __init__.py
├── builder.py (ContextBuilder)
│   ├── build_context(messages, session_id)
│   ├── retrieve_memories(query)
│   └── format_for_model(messages)
└── manager.py (ContextManager)
    ├── cache_context(session_id, context)
    └── get_cached_context(session_id)
```

## Components

### ContextBuilder

Assembles the final prompt context from:
1. System prompt (from `app/prompt/`)
2. Conversation history (from `app/session/`)
3. Relevant memories (from `app/memory/`)
4. Tool definitions (from `app/tools/`)

### ContextManager

Manages context caching to avoid redundant retrieval:
- In-memory LRU cache (max 100 sessions)
- TTL: 5 minutes
- Auto-invalidate on new messages

## Configuration

- `JARVIS_CONTEXT_MAX_MEMORIES`: Max memories per context (default: 5)
- `JARVIS_CONTEXT_CACHE_TTL`: Cache TTL in seconds (default: 300)

## API

```python
from app.context import ContextBuilder, ContextManager

builder = ContextBuilder(memory_service, session_service)
context = await builder.build_context(messages, session_id)

manager = ContextManager()
manager.cache_context(session_id, context)
```
