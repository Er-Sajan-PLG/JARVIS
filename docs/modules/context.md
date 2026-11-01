# Context Builder

**Status**: ACTIVE
**Type**: reference
**Source**: `app/context/` at HEAD
**Last Updated**: 2026-11-01
**Reviewed**: 2026-11-01

---

## Overview

Assembles prompt context for LLM conversations within a model token budget,
and trims conversation history to fit.

## Components

### ContextBuilder (`app/context/builder.py`)

Exported from `app.context`. Assembles the final message list from a system
prompt, conversation history, retrieved memories and attached content sources.

- `build_system_prompt(session, assistant_name="JARVIS")` → str
- `assemble_context(session, conversation, sources=None, memories=None, max_context_tokens=8192)` → list[dict]

Memories are rendered with temporal status suffixes (ADR-015).

### ContextWindowManager (`app/context/manager.py`)

Trims conversation messages in user/assistant pairs (never splitting an
exchange) so the total stays within `max_tokens`. Not exported from
`app.context`; import from `app.context.manager`.

- `count_tokens(messages)` / `count_tokens_text(text)`
- `fit(messages, max_tokens=None)` → fitted list

## Configuration

- `JARVIS_CONTEXT_MAX_MEMORIES` is **not** read by this package; memory count
  is controlled by callers. Earlier versions of this document listed env vars
  and an LRU cache/TTL that do not exist here.

## API

```python
from app.context import ContextBuilder
from app.context.manager import ContextWindowManager

builder = ContextBuilder()
messages = builder.assemble_context(session, conversation, memories=mems)

trimmer = ContextWindowManager(max_tokens=4096)
fitted = trimmer.fit(messages)
```
