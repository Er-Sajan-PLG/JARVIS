# Artifact Manager

**Status**: ACTIVE
**Type**: reference
**Source**: `app/artifacts/` at HEAD
**Last Updated**: 2026-09-17

---

## Overview

Manages execution artifacts — intermediate files, outputs, and results from plan execution steps. Provides persistent storage and retrieval for traceability.

## Architecture

```
artifacts/
├── __init__.py
└── manager.py (ArtifactManager)
    ├── store_artifact(plan_id, step_id, data)
    ├── get_artifact(artifact_id)
    ├── list_artifacts(plan_id)
    └── delete_artifact(artifact_id)
```

## Storage

- Backend: filesystem (`~/jarvis_artifacts/` by default)
- Format: JSON-serialized step outputs
- Configurable via `JARVIS_ARTIFACT_PATH` env var

## Lifecycle

1. Plan execution starts → artifacts directory created per plan
2. Each step stores output as `<step_id>.json`
3. Plan completion → artifacts retained for audit
4. Manual cleanup via `delete_workspace_path` tool

## API

```python
from app.artifacts import ArtifactManager

manager = ArtifactManager()
artifact_id = await manager.store_artifact("plan-123", "step-1", {"output": "data"})
result = await manager.get_artifact(artifact_id)
```
