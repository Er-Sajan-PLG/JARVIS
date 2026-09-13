# ADR-010: Adapters & Integrations Boundary Isolation


**Status**: ACTIVE
**Last Updated**: 2026-07-28
- **Status**: Approved
- **Date**: 2026-07-28
- **Version Tag**: `v3.0.0 Refactored`
- **Commit**: `ec0dc4e`
- **Confidence**: `VERIFIED`

## Context
Directly coupling external HTTP/WebSocket web frameworks or third-party open-source libraries (ChromaDB, PaddleOCR, PyMuPDF) to internal cognitive services creates messy import graphs and vendor coupling.

## Decision
Enforce strict **Adapters & Integrations Boundary Isolation**:
1. `app/adapters/`: Contains all I/O protocol entry points (FastAPI REST HTTP routes, WebSocket / SSE streaming endpoints, Bearer token authentication).
2. `app/integrations/`: Contains all third-party open-source library wrappers (PaddleOCR, PyMuPDF, ChromaDB vector stores).
3. Core domain entities (`app/domain/`) and Cognitive Brain services (`app/brain/`) MUST NOT import from `adapters/` or `integrations/` directly.

## Consequences
- **Positive**: Clean inward-pointing dependency architecture; third-party libraries can be swapped without touching core business logic.
- **Negative**: Adds explicit wrapper classes in `app/integrations/`.
