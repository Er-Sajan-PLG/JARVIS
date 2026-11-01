# Artifact Manager

**Status**: ACTIVE
**Type**: reference
**Source**: `app/artifacts/` at HEAD
**Last Updated**: 2026-11-01
**Reviewed**: 2026-11-01

---

## Overview

Manages disk spillover storage for binary content artifacts (PDFs, images,
repositories, uploads). Spills in-memory bytes to disk and returns
`ContentSource` / `ArtifactHandle` domain models for downstream use.

## Architecture

```
artifacts/
├── __init__.py          # exports ArtifactManager
└── manager.py (ArtifactManager)
    ├── spill_bytes(content_bytes, filename, mime_type, metadata)
    ├── spill_stream(stream, filename, mime_type)
    └── get_artifact_bytes(artifact)
```

## Storage

- Backend: filesystem (`data/artifacts/` by default)
- Format: raw bytes written under a content-hash filename
- Configurable via constructor `storage_dir` (no env var; the default is
  `data/artifacts`)

## API

```python
from app.artifacts import ArtifactManager

manager = ArtifactManager()
handle = manager.spill_bytes(b"...raw bytes...", "report.pdf", "application/pdf")
data = manager.get_artifact_bytes(handle)
```

## Notes

- Artifact IDs are derived from the SHA-256 of the content (first 16 hex
  chars), so identical content is stored once.
- `spill_stream` reads the whole stream into memory before spilling.
- There is no `store_artifact` / `get_artifact` / `list_artifacts` /
  `delete_artifact` API and no `JARVIS_ARTIFACT_PATH` env var; earlier
  versions of this document described them, but they never existed.
