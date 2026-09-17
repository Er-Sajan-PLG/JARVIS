# AGY CLI Integration

**Status**: ACTIVE
**Type**: reference
**Source**: `app/adapters/integrations/agy.py` at HEAD
**Last Updated**: 2026-09-17

---

## Overview

Integration with the AGY CLI (Antigravity IDE command-line interface). Provides programmatic access to AGY IDE features from JARVIS.

## Architecture

```
agy.py (AGYClient)
├── CLI wrapper for `agy` commands
├── File analysis (analyze-file)
└── Model listing (models)
```

## API

```python
from app.adapters.integrations.agy import AGYClient

client = AGYClient()
models = await client.list_models()
analysis = await client.analyze_file("path/to/file.py")
```

## Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/agy/models` | List available AGY models |
| GET | `/agy/status` | Get AGY CLI status |
| POST | `/agy/analyze-file` | Analyze a file with AGY |

## Dependencies

- AGY CLI must be installed and in PATH
- Configured via `AGY_CLI_PATH` env var (default: `agy`)
