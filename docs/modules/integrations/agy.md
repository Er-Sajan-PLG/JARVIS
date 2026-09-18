# AGY CLI Integration

**Status**: ACTIVE
**Type**: reference
**Source**: `app/adapters/integrations/agy.py` at HEAD
**Last Updated**: 2026-09-19

---

## Overview

Integration with the AGY CLI (Antigravity IDE command-line interface, `agy`
v1.2.6 at `~/.local/bin/agy`). Provides programmatic access to Google AI Pro
models from JARVIS with no API key — the CLI uses the locally signed-in
Google session. Default model: `gemini-3.8-flash-medium`.

## Architecture

```
app/adapters/integrations/agy.py (module functions, all sync)
├── _agy_which / is_available — PATH + well-known locations
├── get_models — `agy models`, tab-separated slug/name parsing
├── chat — `agy --print= --output-format json` (+ threading/passthrough)
└── analyze_file — local read (60k cap) inlined into a chat prompt
```

There is no `AGYClient` class and no `AGY_CLI_PATH` env var (older versions
of this doc described both; neither ever existed). All functions are sync;
callers in async paths run them directly (subprocess, bounded by timeout).

## API

```python
from app.adapters.integrations.agy import chat, get_models, analyze_file

models = get_models()
result = chat(
    [{"role": "user", "content": "Summarize this."}],
    model="gemini-3.8-flash-medium",
    effort="medium",
    conversation_id="jarvis-<session>",  # server-side threading
    agent="plan",                         # optional worker profile
    mode="plan",                          # plan | accept-edits
    add_dirs=["./scope"],                 # optional scoping
)
# result: {content, model, tokens_used, finish_reason, conversation_id}
text = analyze_file("path/to/file.py", "What does this do?", mime_type="text/x-python")
```

Notes: `--print-timeout` rounds UP to whole minutes (90 s → `2m`); token
usage comes from the CLI JSON `usage` block when present; `analyze_file`
has no native upload yet (inline + cap, MIME hint inlined).

## Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/agy/models` | List available AGY models |
| GET | `/agy/status` | Get AGY CLI status |
| POST | `/agy/analyze-file` | Analyze a file with AGY |

## Chat wiring

`POST /api/chat` with `{"provider": "agy"}` routes through `agy.chat`
(`app/adapters/web/router.py`): per-session `conversation_id`
(`jarvis-<session_id>`), optional `effort` via top-level `effort` or the
`agy` options object (`agent`, `mode`, `conversation_id` overrides).

## Dependencies

- AGY CLI must be installed and in PATH (`~/.local/bin/agy` is the known
  location; `shutil.which` first, then well-known paths)
