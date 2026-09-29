# JARVIS API Contract

**Status**: ACTIVE
**Type**: reference
**Source**: `app/adapters/http/router.py`, `app/adapters/websocket/`, `app/adapters/web/*.py`, `app/api/ocr/routes.py`, `app/main.py` at HEAD
**Last Updated**: 2026-09-18
**Reviewed**: 2026-09-18

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
`is_authorized` in `app/adapters/security.py`. `validate_api_key`
(`app/adapters/http/router.py:34-48`) is a thin FastAPI dependency over it:

```python
async def validate_api_key(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> bool:
    if is_authorized(authorization=authorization, x_api_key=x_api_key):
        return True
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
```

`is_authorized` reads `JARVIS_API_KEY` from the environment; when it is unset
(local development) every request is allowed. Otherwise the presented
`Authorization: Bearer <key>` / `X-API-Key: <key>` credential must match, and
the comparison uses `hmac.compare_digest`, so a wrong key cannot be recovered
byte-by-byte from response timing. A failed check surfaces as `401` with
`{"detail": "Unauthorized"}`. The web-console router (`app/adapters/web/router.py:94-117`)
applies the same rule router-wide (headers only — never the query string).

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

**Auth**: None — liveness probe, no dependency on `validate_api_key`
(`app/adapters/http/router.py:51-60`).

**Response 200**:
```json
{
  "status": "healthy",
  "service": "JARVIS",
  "version": "v3.x.x",
  "tools_registered": 12
}
```

---

### 3.1.1 Readiness Check

```http
GET /api/v1/ready
```

**Auth**: None — readiness probe, independent of `validate_api_key`
(`app/adapters/http/router.py:64-112`).

Liveness (`/health`) answers *"is the process up?"*; readiness answers *"should
this instance receive traffic?"*. A container can be live while no model is
resolvable, in which case a chat request fails anyway. The probe is **total**: it
returns 200 with a per-subsystem verdict rather than a 5xx, so the caller always
learns *which* part is down.

**Response 200**:
```json
{
  "ready": true,
  "checks": {
    "model": "ok: openrouter/qwen/qwen3-coder:free",
    "memory_service": "ok",
    "mode_manager": "ok"
  },
  "version": "v3.x.x"
}
```

Each `checks` value is `"ok"` or `"down: <reason>"`; `ready` is true only when
every check starts with `ok`.

The `model` check follows the **request path** — whether a default model resolves
via `adapters/web/settings.get_default()` — not `container.model_router`. That
router has **zero `BaseLLMProvider` implementations** in the tree (verified: only
`MagicMock` constructs one in tests); its failover intent is already served by
`OmniModelClient` over the `ModelClient` protocol. Probing it reported a
subsystem nothing reads as if it were load-bearing.

`agy` is a CLI-backed pseudo-provider (`app/adapters/integrations/agy.py`) the
console reaches directly and the HTTP path cannot. When it is the default, the
check reports `"ok: agy/<model> (console path only)"` — available to the console,
deliberately not claimed for the REST synthesis path.

> **Note (2026-09-29)**: this endpoint did not previously exist. It was asserted
> by `docs/SPRINT_1_2_COMPLETION.md:40` ("/ready + /metrics … verified live 200")
> although no route was ever registered — git history contains no `/ready`
> handler. `GET /metrics` remains **unimplemented**; the only metrics surface is
> the in-process `MetricsCollector` (`app/telemetry/metrics.py`), which is not
> exposed over HTTP.

---

### 3.2 Chat Completions (Primary Interface)

```http
POST /api/v1/chat/completions
Content-Type: application/json
Authorization: Bearer <JARVIS_API_KEY>
```

**Request** (`app/adapters/http/router.py:74-83` — `messages[]` wins, `prompt` is the
fallback, a missing prompt degrades to `""` and never 500s):
```json
{
  "messages": [{"role": "user", "content": "summarise inbox"}],
  "prompt": "summarise inbox",
  "session_id": "string (optional, default: 'default_session')"
}
```

**Response 200** — statuses are lowercase lifecycle words, plus tool metadata
and any paused HITL steps:
```json
{
  "session_id": "string",
  "plan_id": "string",
  "status": "completed | running | failed",
  "steps_count": 5,
  "complexity": "DIRECT_CHAT | FILE_QUERY | TOOL_SEARCH | MULTI_STEP",
  "requires_tools": true,
  "awaiting_approval": []
}
```

The keys above are **unconditional**. With `JARVIS_HTTP_LLM=1` the response
additionally carries synthesized answer text
(`app/adapters/http/synthesis.py`):

```json
{
  "response": "the model's answer",
  "model": {"provider": "openrouter", "id": "qwen/qwen3-coder:free"},
  "tokens_used": 123,
  "memories_used": 2
}
```

Or, when no default model is configured or the provider is unreachable, exactly
one of:

```json
{ "synthesis_error": "Model request failed: ..." }
```

Synthesis is **additive**: a synthesis failure never removes the plan fields and
never turns a successful plan into a 5xx. With the flag off (the default) no
`response` or `synthesis_error` key appears at all, so HITL consumers are
unaffected either way. See `docs/CONFIG.md` for the flag.

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

### 3.4 HITL (Human-in-the-Loop) Endpoints

```http
GET /api/v1/hitl/pending
```

**Auth**: Required

**Query params**:
- `include_decided` (bool, optional) — include already-decided requests

**Response 200** (`app/adapters/http/router.py:115-123`; record shape is
`PendingApproval.to_dict` from `app/guardrails/approvals.py:149-165`):
```json
{
  "count": 1,
  "pending": [
    {
      "plan_id": "plan-abc",
      "step_id": "step-1",
      "title": "Delete /tmp/old.log",
      "tool_name": "delete_file",
      "description": "…",
      "safety_tier": "DESTRUCTIVE",
      "requested_at": "2026-09-18T00:00:00+00:00",
      "notified_at": null,
      "decided": false,
      "decision": null,
      "approver": null,
      "reason": "",
      "decided_at": null
    }
  ]
}
```

```http
POST /api/v1/hitl/approve
Content-Type: application/json
```

**Auth**: Required. Shipped — approving resumes the plan, denying skips the
destructive step and resumes the remainder.

**Request** (`app/adapters/http/router.py:126-139`):
```json
{
  "plan_id": "plan-abc (required)",
  "step_id": "step-1 (required)",
  "decision": "approve | deny (or approved: true/false alias)",
  "approver": "telegram:12345 (optional, default: 'unknown')",
  "reason": "optional justification, recorded on deny"
}
```

**Response 200**:
```json
{
  "decision": {"plan_id": "plan-abc", "step_id": "step-1", "decision": "approve"},
  "plan_id": "plan-abc",
  "status": "completed | running | failed",
  "steps_count": 5,
  "awaiting_approval": []
}
```

**Errors**: `422` when `plan_id`/`step_id`/`decision` are missing or invalid,
`404` for an unknown approval, `409` for a second decision on the same step.

```http
POST /api/v1/hitl/notified
Content-Type: application/json
```

**Auth**: Required. Idempotent delivery marker (first timestamp wins) so a
polling workflow does not re-announce the same approval on every tick.

**Request** (`app/adapters/http/router.py:199-218`):
```json
{
  "plan_id": "plan-abc (required)",
  "step_id": "step-1 (required)"
}
```

**Response 200**:
```json
{"notified": {"plan_id": "plan-abc", "step_id": "step-1"}}
```

**Errors**: `422` when `plan_id`/`step_id` are missing, `404` for an unknown approval.

---

## 4. WebSocket Endpoints (`/ws/`)

### 4.1 WebSocket Chat (`/ws/chat/{session_id}`)

```http
GET /ws/chat/{session_id}
Upgrade: websocket
Authorization: Bearer <JARVIS_API_KEY>
```

Legacy clients connect at `/ws/chat` (or `/ws`, same handler) and land on the
`default` session (`app/adapters/websocket/stream.py:59-63`).

**Auth**: Required — `Authorization: Bearer <key>`, `X-API-Key: <key>`, or
`?api_key=<key>` on the connect URL (browsers cannot set headers on a WebSocket).
An unauthenticated or wrongly-keyed upgrade is closed with **1008 Policy
Violation** before any application message is sent.

**Protocol**: Bidirectional JSON streaming

**Client → Server** — the prompt is read from `content`, falling back to
`prompt`, then `message` (`app/adapters/websocket/stream.py:29`):
```json
{
  "content": "user message (or prompt | message)"
}
```

**Server → Client (Stream)** — exactly these four frames, no step-status or
HITL frames on this socket:
```json
// Intent analysis
{"type": "intent_analysis", "complexity": "MULTI_STEP", "requires_tools": true}

// Token chunks (streaming)
{"type": "token_chunk", "content": "partial response"}

// Stream end
{"type": "stream_end"}

// Failures
{"type": "error", "content": "…"}
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

## 5. Web Console API (`/api/*`)

Router-level auth (`app/adapters/web/router.py:94-124`): every endpoint below
requires `Authorization: Bearer <key>` or `X-API-Key: <key>`; query-string keys
stay disabled. (`POST /api/upload` additionally carries the dependency
explicitly — same rule, belt and braces.)

### 5.1 Chat

```http
POST /api/chat
Content-Type: application/json
```

**Auth**: Required.

**Request**: `message` (or attached `files`) is required, `400` otherwise.
`model` arrives as a dict (`{"provider","id"}`) or a bare string id resolved
against the live catalogue, falling back to the saved default. Mail/brief
questions inject an unread-email digest / generated-brief context; Telegram
sessions requesting voice delivery set `voice_sent`.

```json
{
  "message": "any important email?",
  "model": {"provider": "openrouter", "id": "x-ai/grok-4.20"},
  "session_id": "telegram:12345 (optional, default: random uuid)",
  "memory_enabled": true,
  "files": [],
  "file_contents": [{"name": "notes.md", "content": "…"}]
}
```

**Response 200**:
```json
{
  "response": "…",
  "model": {"provider": "openrouter", "id": "x-ai/grok-4.20"},
  "session_id": "telegram:12345",
  "tokens_used": 123,
  "voice_sent": false
}
```

Model failures return `200` with `{"error": "Model request failed: …"}`;
unknown provider / missing key / no model selected return `400`.

### 5.2 Files & Upload

```http
GET /api/files?q=&kind=
GET /api/files/{file_id}
GET /api/files/{file_id}/download
DELETE /api/files/{file_id}
POST /api/upload
```

**Auth**: Required (all five).

- `GET /api/files` lists uploads newest-first; `q` filters by filename,
  `kind` by `pdf | image | spreadsheet | text | other`. → `{"files": [], "total": 0}`
- `GET /api/files/{file_id}` returns metadata plus an extracted-text `preview`
  (first 20000 chars). `404` when unknown.
- `GET /api/files/{file_id}/download` streams the stored bytes. `404` when unknown.
- `DELETE /api/files/{file_id}` removes the upload. → `{"success": true, "deleted": "<id>"}`
- `POST /api/upload` (multipart `file`) stores under `data/uploads/` and returns
  extracted text (images / non-extractable files get a placeholder note):

```json
{
  "file_id": "uuid",
  "filename": "notes.md",
  "size": 42,
  "content_type": "text/markdown",
  "kind": "text",
  "extracted_text": "… (first 50000 chars)"
}
```

### 5.3 Memory

```http
GET /api/memory?session_id=&q=&limit=200
DELETE /api/memory/{memory_id}
GET /api/memories
```

**Auth**: Required (all three). `GET /api/memories` is a frontend alias of
`GET /api/memory` (`app/adapters/web/router.py:1037-1042`).

**Response**: `{"memories": [{"id","value","key","type","category","importance","created_at","valid_at","invalid_at","expired_at","occurs_at"}], "total": 1}`.
`DELETE` → `{"success": true}` (`false` + `error` on failure).

### 5.4 Conversations & Stop

```http
GET /api/conversations
POST /api/conversations
GET /api/conversations/{session_id}
DELETE /api/conversations/{session_id}
POST /api/conversations/{session_id}/pin
POST /api/stop
```

**Auth**: Required (all six).

- `GET /api/conversations` → `{"conversations": []}`
- `POST /api/conversations` (`{"session_id"}` optional) → `{"session_id": "…", "created": true}`
- `GET /api/conversations/{session_id}` → `{"session_id": "…", "exists": true}`
- `DELETE /api/conversations/{session_id}` wipes every memory tied to the
  session → `{"success": true, "deleted_memories": 0}`
- `POST /api/conversations/{session_id}/pin` (`{"message_id"}`) →
  `{"success": true, "pinned": "…"}`
- `POST /api/stop` → `{"status": "stopped"}`

### 5.5 Models

```http
GET /api/models
POST /api/models/select
```

**Auth**: Required (both). `GET` is served by the first-registered handler
(`list_models`, `app/adapters/web/router.py:281-284`) and returns the live
per-provider catalogue with availability status; the flat frontend-picker
listing (`get_models`) is registered second on the same path.

**Request** (`POST`):
```json
{"model_id": "x-ai/grok-4.20", "backend": "openrouter", "model": "x-ai/grok-4.20"}
```

**Response**: `{"active": "openrouter/x-ai/grok-4.20", "name": "x-ai/grok-4.20"}`
(stored as the default).

### 5.6 Settings

```http
GET /api/settings/default
POST /api/settings/default
GET /api/settings/providers
POST /api/settings/providers
DELETE /api/settings/providers/{key}
POST /api/settings/providers/fetch-models
GET /api/settings/models
POST /api/settings/models
DELETE /api/settings/models/{provider}/{model_id:path}
POST /api/settings/models/hide
GET /api/settings/api-keys
POST /api/settings/api-keys
DELETE /api/settings/api-keys/{provider}
```

**Auth**: Required (all). Bodies carry `provider`/`model`/`base_url`/`api_key`
fields as appropriate (`400` when required fields are missing);
`POST /api/settings/providers/fetch-models` probes an OpenAI-compatible
`/models` endpoint and returns `{"models": [], "error": …}` on failure.
`GET /api/settings/api-keys` returns only `{"keys": {"openrouter":
{"configured": true, "source": "stored|env"}}}` — credential values never
cross the wire; masked/empty saves are ignored.

### 5.7 AGY (Google AI Pro via Antigravity CLI)

```http
GET /api/agy/status
GET /api/agy/models
POST /api/agy/analyze-file
```

**Auth**: Required (all three).

- `GET /api/agy/status` → `{"available": true}`
- `GET /api/agy/models` → `{"models": []}`
- `POST /api/agy/analyze-file` (`{"file_path"}` required, `400` otherwise;
  optional `query`, `model`) → `{"response": "…"}` or `{"error": "…"}`.

### 5.8 Console Health

```http
GET /api/health
```

**Auth**: Required. → `{"status": "ok", "service": "JARVIS Web API"}`.

---

## 6. Service APIs (`/api/v1/*`)

All routers below gate on `validate_api_key` (`app/adapters/http/router.py:34-48`),
so Bearer / `X-API-Key` headers are required and the query-string form is not
accepted — except the public VAPID key.

### 6.1 Emails (`app/adapters/web/email_routes.py`)

```http
GET /api/v1/emails/accounts
GET /api/v1/emails/?folder=INBOX&limit=50&unread_only=false&account=
GET /api/v1/emails/search?query=&limit=20&account=
GET /api/v1/emails/{email_id}?account=
POST /api/v1/emails/
POST /api/v1/emails/{email_id}/reply
```

- `POST /api/v1/emails/` (`{"to","subject"}` required, `400` otherwise; plus `body`)
  sends a message.
- `POST /api/v1/emails/{email_id}/reply` (`{"body"}` required) replies.
- Backend failures surface as `500`; unknown id as `404`.

### 6.2 Notify (`app/adapters/web/notify_routes.py`)

```http
POST /api/v1/notify/
Content-Type: application/json
```

One endpoint for every "tell the operator something" path. `body` is required
(`400`); `channels` defaults to `["push"]` and only `push | telegram | whatsapp`
are accepted (`400` on unknown). Unconfigured channels skip with
`{"success": false, "error": "… not configured"}` instead of failing the alert.

```json
{
  "title": "JARVIS",
  "body": "Backup finished",
  "channels": ["push", "telegram"],
  "data": {},
  "chat_id": "telegram override (optional)"
}
```

**Response**: `{"success": true, "results": {"push": {}, "telegram": {}}}`.

### 6.3 Push (`app/adapters/web/push_routes.py`)

```http
GET /api/v1/push/vapid-public-key
POST /api/v1/push/subscribe
DELETE /api/v1/push/unsubscribe
POST /api/v1/push/test
GET /api/v1/push/status
```

- `GET /api/v1/push/vapid-public-key` is **public** (no auth — the browser needs
  it before any credential exists). → `{"publicKey": "…"}`; `503` when
  `VAPID_PUBLIC_KEY` is unset.
- `POST /api/v1/push/subscribe` (`{"endpoint","keys"}` required) →
  `{"success": true, "message": "Subscribed", "count": 1}`.
- `DELETE /api/v1/push/unsubscribe` (`{"endpoint"}` required) →
  `{"success": true, "message": "Unsubscribed", "count": 0}`.
- `POST /api/v1/push/test` (`{"title","body"}` optional) → `{"success": true, "result": {}}`.
- `GET /api/v1/push/status` → `{"subscriptions": 0, "vapid_configured": false}`.

### 6.4 Morning Brief (`app/adapters/web/brief_routes.py`)

```http
GET /api/v1/brief/
POST /api/v1/brief/deliver
GET /api/v1/brief/status
```

- `GET /api/v1/brief/` generates and returns the brief object.
- `POST /api/v1/brief/deliver` generates and delivers →
  `{"success": true, "brief": {}, "delivery_results": {}}`.
- `GET /api/v1/brief/status` →
  `{"enabled": true, "time": "07:00", "delivery_channels": []}`.

### 6.5 Voice (`app/adapters/web/voice_routes.py`)

```http
POST /api/v1/voice/stt
POST /api/v1/voice/tts
GET /api/v1/voice/status
```

STT runs locally via faster-whisper; TTS via Edge TTS (no API key).
Request/response only — nothing streams.

- `POST /api/v1/voice/stt` (multipart `audio`, 10 MB max; `400` empty,
  `413` oversize) → `{"success": true, "text": "…"}`.
- `POST /api/v1/voice/tts` (`{"text"}` required, optional `voice`) returns raw
  MP3 bytes (`audio/mpeg`).
- `GET /api/v1/voice/status` →
  `{"stt_model": "tiny", "stt_loaded": false, "tts_voice": "en-US-ChristopherNeural"}`.

---

## 7. OCR (`/api/ocr/*`)

No auth dependency (`app/api/ocr/routes.py`). Multipart upload surface.

```http
GET /api/ocr/health
POST /api/ocr/process
POST /api/ocr/process-path
```

- `GET /api/ocr/health` → OCR service/model health (`HealthResponse`).
- `POST /api/ocr/process` (multipart `file` plus form fields `backend`
  (`auto | unlimited | paddle`), `mode` (`gundam | base`), `prompt`,
  `ngram_window`, `max_tokens`, `paddle_mode`, `dpi`, `return_json`) →
  `OCRResult`. Rejects unsupported extensions (`400`) and oversize files
  (`413`); service failures surface as `502`.
- `POST /api/ocr/process-path` (form `file_path` of a server-side file plus
  `backend`/`mode`/`prompt`/`dpi`) → `OCRResult`; `404` when the path is missing.

---

## 8. Installable-App (PWA) Surface

Served unauthenticated from `app/main.py` at the origin root (a browser fetches
these before any credential exists — gating them would make the app
uninstallable and block service-worker registration):

```http
GET /
GET /manifest.json
GET /service-worker.js
GET /offline.html
```

- `/` serves `frontend/index.html` (console shell).
- `/manifest.json` serves `frontend/assets/manifest.json`.
- `/service-worker.js` serves `frontend/assets/service-worker.js` with
  `Service-Worker-Allowed: /` so the worker controls navigations.
- `/offline.html` serves `frontend/offline.html` (precached fallback).
- Icons live at `/icon-192.png`, `/icon-512.png` (plus `/badge.png`), served
  from `frontend/assets/` with `GET` and `HEAD`.
- `/static/` mounts `frontend/assets/` (falling back to `frontend/`).

---

## 9. Error Responses

### 9.1 Standard Error Format

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

### 9.2 HTTP Status Codes

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

## 10. Data Models

### 10.1 IntentAnalysis
```python
class IntentAnalysis:
    complexity: Literal["DIRECT_CHAT", "FILE_QUERY", "TOOL_SEARCH", "MULTI_STEP"]
    requires_tools: bool
    safety_flags: List[SafetyFlag]
```

### 10.2 ExecutionPlan
```python
class ExecutionPlan:
    plan_id: str
    steps: List[ExecutionStep]
    status: Literal["PENDING", "RUNNING", "COMPLETED", "AWAITING_APPROVAL", "FAILED"]
```

### 10.3 ExecutionStep
```python
class ExecutionStep:
    step_id: str
    tool: str
    params: dict
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "AWAITING_APPROVAL"]
    result: Any
    safety_tier: Literal["SAFE", "SENSITIVE", "DESTRUCTIVE"]
```

### 10.4 MemoryRecord
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

## 11. n8n Integration Patterns

### 11.1 n8n → JARVIS: Chat Completion

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

### 11.2 n8n → JARVIS: Health Check (Pre-deploy)

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

### 11.3 JARVIS → n8n: HITL Callback

When JARVIS emits `HITLRequestEvent` (DESTRUCTIVE tool), n8n `JARVIS-HITL` workflow:
1. Receives webhook with approval request
2. Presents to human (Slack/Email/Telegram)
3. On approval → calls back to JARVIS with `approved: true`
4. JARVIS resumes execution

---

## 12. Rate Limits & Quotas (Planned)

| Tier | Requests/Min | Tokens/Min | Scope |
|------|--------------|------------|-------|
| Default | 60 | 100,000 | Per API key |
| n8n | 300 | 500,000 | Per workflow |

---

## 13. Versioning & Deprecation

| Version | Status | Deprecation Date |
|---------|--------|------------------|
| v1 | **CURRENT** | N/A |
| v0 | DEPRECATED | 2026-07-28 (removed) |

**Policy**:
- Breaking changes → MAJOR version → new URL prefix (`/api/v2/`)
- 90-day deprecation window for MINOR removals
- All changes announced in CHANGELOG.md

---

## 14. OpenAPI Spec

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

## 15. Testing Contract

| Endpoint | Contract Test | CI Gate |
|----------|---------------|---------|
| `GET /api/v1/health` | Returns 200 + expected fields, no auth | ✅ Required |
| `POST /api/v1/chat/completions` | Valid request → valid response schema | ✅ Required |
| `/ws/chat/{session_id}` | Connect → send → receive stream | ✅ Required |
| Auth | Missing key → 401 | ✅ Required |
| Auth | Invalid key → 401 | ✅ Required |

---

## 16. Shipped Since Last Review

| Endpoint | Shipped as | Note |
|----------|------------|------|
| `POST /api/v1/hitl/approve` | `POST /api/v1/hitl/approve` (§3.4) | Was "planned"; shipped with approve/deny + resume |
| `GET /api/v1/models` (planned path) | `GET /api/models` (§5.5) | Lives on the console router, not `/api/v1/` |
| `POST /api/v1/models/select` (planned path) | `POST /api/models/select` (§5.5) | Same — console router |
| `GET /api/v1/memories` (planned) | `GET /api/memory`, `GET /api/memories` (§5.3) | Read-only list + alias; no `POST` store endpoint, no sessions endpoint |

---

**Next**: See `CAPABILITY_TRACKER.md` for Capability Contract v1.0 compliance tracking.
