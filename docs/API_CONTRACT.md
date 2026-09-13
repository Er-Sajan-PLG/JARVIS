# JARVIS API Contract

**Status**: ACTIVE
**Type**: reference
**Source**: `app/api/` at HEAD
**Last Updated**: 2026-09-13

**Authentication**: Bearer Token (`JARVIS_API_KEY`) + X-API-Key header
**Workflow Orchestration**: n8n (external)

---

## 1. API Overview

| Aspect | Specification |
|--------|---------------|
| **Base URL** | `http://localhost:8000` (dev), `https://jarvis.yourdomain.com` (prod) |
| **Protocol** | HTTP/1.1, HTTP/2, WebSocket, SSE |
| **Auth** | Bearer Token (`Authorization: Bearer <JARVIS_API_KEY>`) or `X-API-Key` header |
| **Content-Type** | `application/json` (request/response) |
| **Versioning** | URL prefix `/api/v1/` |
| **Rate Limiting** | Not yet implemented (planned) |
| **CORS** | Configurable via `CORS_ALLOWED_ORIGINS` env var |

---

## 2. Authentication

### 2.1 Bearer Token (Primary)

```http
Authorization: Bearer <JARVIS_API_KEY>
```

### 2.2 X-API-Key Header (Alternative)

```http
X-API-Key: <JARVIS_API_KEY>
```

### 2.3 Validation Logic

The credential decision is shared by every surface through
`app/adapters/security.py:is_authorized`; `validate_api_key`
(`app/adapters/http/router.py`) raises `HTTPException(401)` when it returns false.

```python
expected = os.environ.get("JARVIS_API_KEY", "").strip()
if not expected:
    return True  # Dev fallback — no key configured, all requests allowed

presented = bearer_token or x_api_key          # header forms
if not presented or not hmac.compare_digest(presented, expected):
    raise HTTPException(401, "Unauthorized")
```

Credentials are compared with `hmac.compare_digest`, so a wrong key cannot be
recovered byte-by-byte from response timing.

### 2.4 Streaming Surfaces (WebSocket / SSE)

A browser cannot attach request headers to a `WebSocket` or an `EventSource`, so
the two streaming endpoints additionally accept the key as an `api_key` **query
parameter**:

```http
GET /ws/stream?prompt=hello&api_key=<JARVIS_API_KEY>
```

Query-string credentials can be captured by access logs and browser history, so
this form is opt-in and used **only** by the streaming surfaces; the REST surface
does not accept it. Header forms still work for non-browser clients (n8n, curl).

### 2.5 n8n Integration

- n8n stores `JARVIS_API_KEY` in **encrypted credentials**
- All n8n → JARVIS calls use Bearer header
- Key rotation via n8n workflow (90-day schedule)

---

## 3. REST Endpoints (`/api/v1/`)

### 3.1 Health Check

```http
GET /api/v1/health
```

**Auth**: Required (Bearer/X-API-Key)

**Response 200**:
```json
{
  "status": "healthy",
  "system": "JARVIS v3.0",
  "providers_registered": ["local_general", "grok", "openrouter", "google_general"]
}
```

**Response 401**:
```json
{
  "detail": "Invalid or missing JARVIS_API_KEY authentication credentials"
}
```

---

### 3.2 Chat Completions (Primary Interface)

```http
POST /api/v1/chat/completions
Content-Type: application/json
Authorization: Bearer <JARVIS_API_KEY>
```

**Request**:
```json
{
  "prompt": "string (required)",
  "session_id": "string (optional, default: 'default_session')"
}
```

**Response 200**:
```json
{
  "session_id": "string",
  "plan_id": "string",
  "status": "COMPLETED | AWAITING_APPROVAL | FAILED",
  "steps_count": 5,
  "complexity": "DIRECT_CHAT | FILE_QUERY | TOOL_SEARCH | MULTI_STEP"
}
```

**Response 401**: Auth error (see above)

**Response 500**: Internal error (logged with correlation ID)

---

### 3.3 Intent Complexity Classification

| Complexity | Description | Tools Required |
|------------|-------------|----------------|
| `DIRECT_CHAT` | Simple conversation, no tools | No |
| `FILE_QUERY` | Read/analyze files | Yes (file tools) |
| `TOOL_SEARCH` | Search/execute tools | Yes (tool tools) |
| `MULTI_STEP` | Multi-step planning | Yes (multiple tools) |

---

## 4. WebSocket Endpoints (`/ws/`)

### 4.1 WebSocket Chat (`/ws/chat`)

```http
GET /ws/chat
Upgrade: websocket
Authorization: Bearer <JARVIS_API_KEY>
```

**Auth**: Required — `Authorization: Bearer <key>`, `X-API-Key: <key>`, or
`?api_key=<key>` on the connect URL (browsers cannot set headers on a WebSocket).
An unauthenticated or wrongly-keyed upgrade is closed with **1008 Policy
Violation** before any application message is sent.

**Protocol**: Bidirectional JSON streaming

**Client → Server**:
```json
{
  "prompt": "user message",
  "session_id": "optional"
}
```

**Server → Client (Stream)**:
```json
// Intent analysis
{"type": "intent_analysis", "complexity": "MULTI_STEP", "requires_tools": true}

// Token chunks (streaming)
{"type": "token_chunk", "content": "partial response"}

// Step execution status
{"type": "step_status", "step_id": "xxx", "status": "RUNNING | COMPLETED | FAILED"}

// HITL request (DESTRUCTIVE tools)
{"type": "hitl_request", "tool": "delete_file", "params": {...}, "approval_id": "xxx"}

// Stream end
{"type": "stream_end"}
```

**Client → Server (HITL Response)**:
```json
{
  "approval_id": "xxx",
  "approved": true
}
```

---

### 4.2 SSE Stream (`/ws/stream`)

```http
GET /ws/stream?prompt=hello&api_key=<JARVIS_API_KEY>
Authorization: Bearer <JARVIS_API_KEY>   # alternative, for non-browser clients
X-API-Key: <JARVIS_API_KEY>              # alternative, for non-browser clients
```

**Auth**: Required — missing or wrong credential returns **401**.

**Response**: Server-Sent Events (text/event-stream)

```
data: {"type": "intent", "complexity": "DIRECT_CHAT"}

data: {"type": "chunk", "content": "JARVIS streaming response..."}

data: [DONE]
```

---

## 5. Error Responses

### 5.1 Standard Error Format

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {},
    "request_id": "uuid"
  }
}
```

### 5.2 HTTP Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | Success | Normal response |
| 400 | Bad Request | Invalid JSON, missing required fields |
| 401 | Unauthorized | Missing/invalid API key |
| 403 | Forbidden | Valid key but insufficient scope (future) |
| 404 | Not Found | Endpoint doesn't exist |
| 422 | Unprocessable | Validation failed |
| 429 | Rate Limited | Not yet implemented |
| 500 | Internal Error | Unexpected failure (logged) |
| 503 | Service Unavailable | All LLM providers down |

---

## 6. Data Models

### 6.1 IntentAnalysis
```python
class IntentAnalysis:
    complexity: Literal["DIRECT_CHAT", "FILE_QUERY", "TOOL_SEARCH", "MULTI_STEP"]
    requires_tools: bool
    safety_flags: List[SafetyFlag]
```

### 6.2 ExecutionPlan
```python
class ExecutionPlan:
    plan_id: str
    steps: List[ExecutionStep]
    status: Literal["PENDING", "RUNNING", "COMPLETED", "AWAITING_APPROVAL", "FAILED"]
```

### 6.3 ExecutionStep
```python
class ExecutionStep:
    step_id: str
    tool: str
    params: dict
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "AWAITING_APPROVAL"]
    result: Any
    safety_tier: Literal["SAFE", "SENSITIVE", "DESTRUCTIVE"]
```

### 6.4 MemoryRecord
```python
class MemoryRecord:
    id: str
    key: str
    value: str
    category: str
    memory_type: Literal["FACT", "EPISODE", "PROCEDURE", "PREFERENCE"]
    created_at: datetime
    score: float  # retrieval relevance
```

---

## 7. n8n Integration Patterns

### 7.1 n8n → JARVIS: Chat Completion

```javascript
// n8n HTTP Request node
{
  "method": "POST",
  "url": "https://jarvis.yourdomain.com/api/v1/chat/completions",
  "authentication": "headerAuth",
  "headerParameters": {
    "Authorization": "Bearer {{$credentials.jarvisApiKey}}",
    "Content-Type": "application/json"
  },
  "body": {
    "prompt": "{{$json.userInput}}",
    "session_id": "{{$json.sessionId}}"
  }
}
```

### 7.2 n8n → JARVIS: Health Check (Pre-deploy)

```javascript
// n8n HTTP Request node
{
  "method": "GET",
  "url": "https://jarvis.yourdomain.com/api/v1/health",
  "authentication": "headerAuth",
  "headerParameters": {
    "Authorization": "Bearer {{$credentials.jarvisApiKey}}"
  }
}
```

### 7.3 JARVIS → n8n: HITL Callback

When JARVIS emits `HITLRequestEvent` (DESTRUCTIVE tool), n8n `JARVIS-HITL` workflow:
1. Receives webhook with approval request
2. Presents to human (Slack/Email/Telegram)
3. On approval → calls back to JARVIS with `approved: true`
4. JARVIS resumes execution

---

## 8. Rate Limits & Quotas (Planned)

| Tier | Requests/Min | Tokens/Min | Scope |
|------|--------------|------------|-------|
| Default | 60 | 100,000 | Per API key |
| n8n | 300 | 500,000 | Per workflow |

---

## 9. Versioning & Deprecation

| Version | Status | Deprecation Date |
|---------|--------|------------------|
| v1 | **CURRENT** | N/A |
| v0 | DEPRECATED | 2026-07-28 (removed) |

**Policy**:
- Breaking changes → MAJOR version → new URL prefix (`/api/v2/`)
- 90-day deprecation window for MINOR removals
- All changes announced in CHANGELOG.md

---

## 10. OpenAPI Spec

**Location**: Auto-generated from FastAPI → `/openapi.json` at runtime

```bash
# Generate static spec for CI
.venv/bin/python -c "
from app.main import app
import json
with open('openapi.json', 'w') as f:
    json.dump(app.openapi(), f, indent=2)
"
```

**Published**: Regenerated from `app.main:app` at runtime. There is no
`JARVIS-Release` workflow — releases are cut with `scripts/bump_version.py`
(version derives from git tags; see `docs/VERSIONING.md`).

---

## 11. Testing Contract

| Endpoint | Contract Test | CI Gate |
|----------|---------------|---------|
| `GET /api/v1/health` | Returns 200 + expected fields | ✅ Required |
| `POST /api/v1/chat/completions` | Valid request → valid response schema | ✅ Required |
| `WS /ws/chat` | Connect → send → receive stream | ✅ Required |
| Auth | Missing key → 401 | ✅ Required |
| Auth | Invalid key → 401 | ✅ Required |

---

## 12. Future Endpoints (Planned)

| Endpoint | Purpose | Sprint |
|----------|---------|--------|
| `GET /api/v1/models` | List available models | 1 |
| `POST /api/v1/models/select` | Switch active model | 1 |
| `GET /api/v1/memories` | Query memory | 2 |
| `POST /api/v1/memories` | Store memory | 2 |
| `GET /api/v1/sessions` | List sessions | 2 |
| `POST /api/v1/hitl/approve` | HITL approval REST fallback | 2 |

---

**Next**: See `CAPABILITY_TRACKER.md` for Capability Contract v1.0 compliance tracking.
