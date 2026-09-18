# Workspace Tools

**Status**: ACTIVE
**Type**: reference
**Source**: `app/tools/workspace_tools.py` at HEAD
**Last Updated**: 2026-09-17

---

## Overview

Tools for managing workspace files, directories, and project structure. Registered with the agent's ToolRegistry for use in conversations.

## Tools

| Tool | Description | Risk |
|------|-------------|------|
| `list_workspace_files` | List files in workspace | low |
| `read_workspace_file` | Read file contents | low |
| `write_workspace_file` | Write file contents | medium |
| `create_workspace_directory` | Create directory | low |
| `delete_workspace_path` | Delete file or directory | destructive |

## Architecture

```
workspace_tools.py
├── ToolDefinition registry
├── @safety_gate decorators
└── File system operations (pathlib-based)
```

## Configuration

- `JARVIS_WORKSPACE_ROOT`: Root directory for workspace operations
- Default: `~/Projects`

## Safety

- All tools use `@safety_gate` decorator
- `delete_workspace_path` requires confirmation (DESTRUCTIVE risk tier)
- Operations are sandboxed to workspace root
