# Technical Debt Ledger & System Roadmap (v0.1.0 to HEAD)

This ledger tracks all technical debt items, architectural bypasses, and temporary hotfixes recorded across the physical history of the JARVIS repository.

---

## 1. Complete Historical Technical Debt Register

| Debt ID | Introduced Commit & Date | Resolution Commit & Date | Status | Root Cause / Reason | Affected Subsystems | Remediation Applied | Confidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `DEBT-001` | `c5a97b4` (2026-07-28) | `ec0dc4e` (2026-07-28) | `RESOLVED` | OCR backends placed under `app/services/ocr/` violating OSS layer boundary | `app/services/ocr/` | Relocated to `app/integrations/ocr/` | `VERIFIED` |
| `DEBT-002` | `b2c2211` (2026-07-05) | `ec0dc4e` (2026-07-28) | `RESOLVED` | Direct ChromaDB vector client calls in memory service without isolation wrapper | `app/memory/` | Wrapped behind `ChromaVectorStore` in `app/integrations/vector/` | `VERIFIED` |
| `DEBT-003` | `f9fa068` (2026-07-18) | `ec0dc4e` (2026-07-28) | `RESOLVED` | Web server REST and WebSocket routes lacked single-tenant API key security | `app/api/server.py` | Added Bearer & X-API-Key `validate_api_key` security dependency in `app/adapters/http/` | `VERIFIED` |
| `DEBT-004` | `1999e53` (2026-06-27) | `ec0dc4e` (2026-07-28) | `RESOLVED` | Unused legacy empty directory `app/project/` | `app/project/` | Removed directory | `VERIFIED` |
| `DEBT-005` | `39b3d5b` (2026-06-27) | `ec0dc4e` (2026-07-28) | `RESOLVED` | Obsolete monolithic `PromptBuilder` class | `app/prompt/builder.py` | Deleted; replaced with Jinja2 `PromptLoader` and `ContextBuilder` | `VERIFIED` |
| `DEBT-006` | `4034bf7` (2026-06-28) | `c5a97b4` (2026-07-28) | `RESOLVED` | Direct synchronous file IO in memory store blocking main thread | `app/memory/store.py` | Mapped memory store to async persistence layer | `VERIFIED` |
| `DEBT-007` | `8519f65` (2026-07-03) | `bb7e20b` (2026-07-28) | `RESOLVED` | Unhandled HTTP 429/503 rate limit crashes in LLM model router | `app/models/router.py` | Built `ResourceManager` with 3-state circuit breaker and failover pool | `VERIFIED` |

---

## 2. Quantitative Debt Summary at HEAD

- **Total Historical Debt Items Recorded**: 7
- **Resolved Debt Items**: 7 (100% resolution rate)
- **Active Technical Debt Items at HEAD**: 0

---

## 3. Future Technical Roadmap & Objectives

1. **Distributed Event Bus Adapter**:
   - Provide Redis Pub/Sub and NATS streaming backend adapters for `InMemoryAsyncBus` to enable multi-node scale-out deployment.
2. **Multi-Modal Tool Guardrails**:
   - Extend `@safety_gate` decorators to validate image binary streams and audio payloads.
3. **Automated Vector Index Re-indexing**:
   - Add background maintenance worker for ChromaDB HNSW vector index optimization.
