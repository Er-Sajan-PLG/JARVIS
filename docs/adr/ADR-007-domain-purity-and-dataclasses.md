# ADR-007: Domain Purity & Standard Dataclasses


**Status**: ACTIVE
**Last Updated**: 2026-07-28
- **Status**: Approved
- **Date**: 2026-07-28
- **Version Tag**: `v3.0.0 Refactored`
- **Commit**: `c5a97b4`
- **Confidence**: `VERIFIED`

## Context
Previous iterations of JARVIS mixed database ORM schemas, Pydantic Web models, and third-party vendor clients directly into business logic modules.

## Decision
Enforce **Domain Purity** in `app/domain/`:
1. All business entities (`ContentSource`, `MemoryRecord`, `ExecutionPlan`, `SessionState`) MUST be standard Python 3.11+ dataclasses (`dataclass`, `field`).
2. Zero infrastructure, database (asyncpg, SQLAlchemy, ChromaDB), or web framework (FastAPI, Starlette) imports permitted in `app/domain/`.
3. All domain entities are re-exported via `__all__` in `app/domain/__init__.py`.

## Consequences
- **Positive**: Domain models are 100% portable, lightweight, fast to instantiate, and independent of external framework changes.
- **Negative**: Requires explicit adapter mapping between external database JSON representations and domain dataclasses.
