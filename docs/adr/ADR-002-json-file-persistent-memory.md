# ADR-002: JSON File Persistent Memory Core

**Status**: HISTORICAL
**Type**: adr
**Last Updated**: 2026-06-28
**Reviewed**: 2026-09-14

- **Status**: Superseded by ADR-004 & ADR-007
- **Date**: 2026-06-28
- **Version Tag**: `v0.5.0`
- **Commit**: `4034bf7`
- **Confidence**: `VERIFIED`

## Context
JARVIS required long-term memory across sessions to store user preferences and identity facts.

## Decision
Implement a file-backed `MemoryStore` saving key-value memory facts into `data/memories.json`.

## Consequences
- **Positive**: Simple, zero-dependency disk persistence.
- **Negative**: Synchronous file IO blocked main execution loop; lacked semantic search capabilities.
