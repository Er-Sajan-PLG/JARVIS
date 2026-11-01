# Workspace Tools

**Status**: ACTIVE
**Type**: reference
**Source**: `app/tools/workspace_tools.py` at HEAD
**Last Updated**: 2026-11-01
**Reviewed**: 2026-11-01

---

## Overview

Tools for managing workspace files and directories. Registered with the
agent's ToolRegistry for use in conversations.

## Tools

| Tool | Description | Risk |
|------|-------------|------|
| `read_file` | Read a file from the workspace (sandboxed) | low |
| `write_file` | Write file contents | medium |
| `append_file` | Append content to a file | medium |
| `create_directory` | Create a directory | medium |

## Architecture

```
workspace_tools.py
├── ToolDefinition registry (WORKSPACE_TOOLS)
├── @safety_gate decorators
└── File system operations (pathlib-based, sandboxed)
```

## Configuration

- `JARVIS_WORKSPACE_ROOT`: Root directory for workspace operations
- Default: `~/Projects`

## Safety

- All tools use `@safety_gate` decorator
- `write_file`, `append_file`, `create_directory` require confirmation
- Operations are sandboxed to the workspace root (and configured extra roots)
- No `delete_*` tool is registered; earlier versions of this document
  listed `delete_workspace_path`, but it does not exist.
