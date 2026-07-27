# JARVIS Master Diagnostic Matrix & Troubleshooting Guide

This document tracks all verified runtime error symptoms, root causes, diagnostic logs, and commit fixes across the complete history of JARVIS from `v0.1.0` to `v3.0.0 Refactored`.

---

# v3.0.0 Refactored
- **Timeline Metadata**: *Feature Author Date: 2026-07-28 (`ec0dc4e`) \| Tag Release Date: 2026-07-28*
## Diagnostic Matrix & Error Fixes
### Verified Bug Fixes & Refactors
#### Release Diagnostic Logs

| Diagnostic Code | Error Symptom | Root Cause | Verifying Test / Commit Fix | Resolution & Remediation |
| :--- | :--- | :--- | :--- | :--- |
| `ERR-3001` | `HTTP 401 Unauthorized` | Request header missing `Authorization: Bearer <key>` or `X-API-Key` | `app/adapters/http/router.py` (`ec0dc4e`) | Add single-tenant `JARVIS_API_KEY` header to HTTP REST/WS calls |
| `ERR-3002` | `Circuit breaker OPENED for provider` | LLM backend returned 429 rate limit or 503 service unavailable | `tests/unit/test_phase2.py` (`bb7e20b`) | `ModelRouter` automatically routes around open circuits to healthy fallback providers |
| `ERR-3003` | `HITLRequiredError: Approval required` | Attempted execution of `DESTRUCTIVE` tool without client approval | `tests/unit/test_phase4.py` (`f4d5e01`) | Client UI must pass `hitl_approvals={step_id: True}` to execute destructive step |
| `ERR-3004` | `Corrupt JSON memory file` | Malformed memory file on disk | `tests/unit/test_issue6.py` (`c5a97b4`) | `MemoryStore` automatically quarantines bad file to `.corrupt-*.bak` and starts clean store |

---

# v3.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 (`81e45f0`) \| Tag Release Date: 2026-07-26*
## Diagnostic Matrix & Error Fixes
### Verified Bug Fixes & Refactors
#### Release Diagnostic Logs

| Diagnostic Code | Error Symptom | Root Cause | Verifying Test / Commit Fix | Resolution & Remediation |
| :--- | :--- | :--- | :--- | :--- |
| `ERR-3000` | `PaddleOCR import error` | Missing optional PaddleOCR binary dependencies | `app/integrations/ocr/service.py` (`2c855c7`) | `OCRService` falls back to `UnlimitedOCRBackend` or plain text extraction |
| `ERR-2999` | `PDF extraction timeout` | Processing unindexed high-res multi-page PDF | `app/knowledge/extract.py` (`e35d468`) | Streamed chunking with per-page page budget caps |

---

# v2.5.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-18 (`f9fa068`) \| Tag Release Date: 2026-07-18*
## Diagnostic Matrix & Error Fixes
### Verified Bug Fixes & Refactors
#### Release Diagnostic Logs

| Diagnostic Code | Error Symptom | Root Cause | Verifying Test / Commit Fix | Resolution & Remediation |
| :--- | :--- | :--- | :--- | :--- |
| `ERR-2500` | `FastAPI CORS error` | Web UI cross-origin request rejected | `app/web_api_server.py` (`f9fa068`) | Configured `CORSMiddleware` with configurable allowed origins |
| `ERR-2501` | `WebSocket connection drop` | Idle ping/pong timeout on streaming connection | `app/adapters/websocket/stream.py` (`f9fa068`) | Client re-connect loop with exponential backoff |

---

# v2.0.0 - v2.4.2
- **Timeline Metadata**: *Feature Author Date: 2026-07-03 (`8519f65`) \| Tag Release Date: 2026-07-03*
## Diagnostic Matrix & Error Fixes
### Verified Bug Fixes & Refactors
#### Release Diagnostic Logs

| Diagnostic Code | Error Symptom | Root Cause | Verifying Test / Commit Fix | Resolution & Remediation |
| :--- | :--- | :--- | :--- | :--- |
| `ERR-2001` | `ChromaDB vector store connection failed` | Missing local sqlite3 or Chroma database directory | `app/memory/vector_retriever.py` (`b2c2211`) | Hybrid search falls back to BM25 keyword search |
| `ERR-2002` | `ModelRouter task classification failed` | Unrecognized prompt task format | `app/models/router.py` (`8519f65`) | Default to `GENERAL` task type and default model |

---

# v0.1.0 - v1.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e13ee67`) \| Tag Release Date: 2026-06-27*
## Diagnostic Matrix & Error Fixes
### Verified Bug Fixes & Refactors
#### Release Diagnostic Logs

| Diagnostic Code | Error Symptom | Root Cause | Verifying Test / Commit Fix | Resolution & Remediation |
| :--- | :--- | :--- | :--- | :--- |
| `ERR-0101` | `Ollama connection refused` | Local Ollama server (`http://localhost:11434`) not running | `app/models/ollama_client.py` (`e13ee67`) | Ensure `ollama serve` is running locally |
| `ERR-0501` | `Memory file permission denied` | `data/memories.json` non-writable | `app/memory/store.py` (`4034bf7`) | Ensure data directory write permissions |
