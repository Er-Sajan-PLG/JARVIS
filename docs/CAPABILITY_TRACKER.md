# JARVIS Capability Contract Tracker

**Status**: ACTIVE
**Type**: register
**Last Updated**: 2026-09-18
**Reviewed**: 2026-09-18

**Contract Version**: 1.0.0
**Contract Source**: `docs/CAPABILITY-CONTRACT.md`
**Review Cadence**: Quarterly (manual review — no `JARVIS-Capability-Sync`
workflow exists; see `docs/GOVERNANCE.md` §3)

---

## 1. Contract Compliance Overview

| Capability Area | Contract Requirement | JARVIS Current | Compliance |
|-----------------|---------------------|----------------|------------|
| **Cognitive Engine** | LangGraph orchestration | ✅ StateGraph + 5 nodes + streaming + OTel + OTLP exporter | ✅ **100%** |
| **Memory Subsystem** | 4-stage pipeline + rich schema | ✅ MemoryPipeline + MemoryItem + embedding dedup | ✅ **100%** |
| **Provider Routing** | Multi-provider + circuit breakers | ✅ 4+ providers | ✅ **100%** |
| **Safety Gate (HITL)** | Tiered + DESTRUCTIVE blocks | ✅ @safety_gate + HITL | ✅ **100%** |
| **MCP Client** | stdio + Streamable HTTP | ✅ Both transports | ✅ **100%** |
| **Session/Checkpoint** | LangGraph MemorySaver | ✅ MemorySaverAdapter + PostgresCheckpointer + fork/archive | ✅ **100%** |
| **Eval Suite** | Regression suite | ✅ 10 evals + CI integration | ✅ **100%** |
| **Web App** | Chat UI + WebSocket | ✅ FastAPI + frontend + WS streaming | ✅ **100%** |
| **MCP Server** | Capability provider to PROFESSOR-J + mesh (chat/brief/notify/email/subagent) | ✅ 17 tools exposed | ✅ **100%** |
| **Voice I/O** | STT + TTS | ✅ faster-whisper STT + Edge TTS (`app/adapters/web/voice_routes.py`) | ✅ **100%** |
| **Comms (email)** | Read + send + reply | ✅ 4 email runner tools (`app/tools/comms_tools.py`) | ✅ **100%** |
| **Morning Brief** | Generate + deliver | ✅ `app/integrations/brief/` + `get_brief` tool | ✅ **100%** |
| **Push Notifications** | Web Push to PWA | ✅ `app/integrations/push/` + `app/adapters/web/push_routes.py` | ✅ **100%** |
| **WhatsApp** | Send-only (receive out of scope) | ⚠️ send-only (`app/integrations/whatsapp/`; see §5 deviation) | ⚠️ **deviation** |

**Overall Compliance**: **100%** (13/13 in-contract capabilities at 100% per the
tables below, plus 1 recorded send-only deviation). This is a manual roll-up
from this document's tables — not a gated measurement; no automated check
derives a compliance percentage. A claim of any other number (a previous
revision said ~97% against these same 100% rows) is inconsistent with the
tables and must not be reintroduced.

---

## 2. Detailed Capability Tracking

### 2.1 Cognitive Engine (Contract §1)

| Contract Requirement | JARVIS Current | Gap | Action |
|---------------------|----------------|-----|--------|
| LangGraph-based orchestration | ✅ `build_cognitive_graph` + `StateGraph[CognitiveState]` | — | Done |
| Typed `CognitiveState` | ✅ `app.domain.cognitive_state.CognitiveState` | — | Done |
| Required nodes (5) | ✅ All 5 nodes in `app.brain.nodes` | — | Done |
| Control flow with `interrupt()` | ✅ conditional edge to END + re-invoke | — | Done |
| Streaming | ✅ `stream_cognitive_loop()` (stream_mode="values") | — | Done |
| OTel spans | ✅ `Tracer` wraps each node via `_wrap()` | — | Done |
| OTLP HTTP exporter | ✅ `app.telemetry.otel_exporter.OTLPExporter` | — | Done |

**Compliance: 100%**

### 2.2 Memory Subsystem (Contract §2)

| Contract Requirement | JARVIS Current | Gap | Action |
|---------------------|----------------|-----|--------|
| 4-stage pipeline | ✅ `MemoryPipeline` façade | — | Done |
| `MemoryItem` schema | ✅ `app.domain.memory.MemoryItem` | — | Done |
| Scope (session/user/global) | ✅ `MemoryScope` enum | — | Done |
| Dense + sparse retrieval | ✅ Hybrid retriever | — | Done |
| Hybrid ranker (0.6/0.4) | ✅ RRF fusion, configurable | — | Done |
| Time-decay + confidence | ✅ `MemoryRanker` | — | Done |
| LLM fact extraction | ✅ `LLMFactExtractor` | — | Done |
| Near-duplicate dedup | ✅ `app.memory.dedup` (embedding + token-overlap) | — | Done |
| Provenance tracking | ✅ `MemoryItem` fields | — | Done |

**Compliance: 100%**

### 2.3 Provider Routing (Contract §3)

| Contract Requirement | JARVIS Current | Gap | Action |
|---------------------|----------------|-----|--------|
| Multi-provider (≥3) | ✅ 4+ providers | — | Done |
| Circuit breaker | ✅ ResourceManager | — | Done |
| Task routing | ✅ TaskType enum | — | Done |
| Structured output | ✅ JSON schema / Pydantic | — | Done |
| Cost tracking | ✅ TokenBudgetManager | — | Done |

**Compliance: 100%**

### 2.4 Safety Gate (Contract §4)

| Contract Requirement | JARVIS Current | Gap | Action |
|---------------------|----------------|-----|--------|
| Tiered (SAFE/SENSITIVE/DESTRUCTIVE) | ✅ `SafetyTier` in `app/domain/plan.py` | — | Done |
| DESTRUCTIVE blocks without HITL | ✅ @safety_gate | — | Done |
| HITL is blocking | ✅ Pauses execution | — | Done |
| Audit log | ✅ InMemoryAsyncBus events | — | Done |

**Compliance: 100%**

### 2.5 Tool/MCP Contract (Contract §5)

| Contract Requirement | JARVIS Current | Gap | Action |
|---------------------|----------------|-----|--------|
| stdio MCP | ✅ `app/integrations/mcp/transports.py` | — | Done |
| Streamable HTTP MCP | ✅ `app/integrations/mcp/transports.py` | — | Done |
| Tool registry | ✅ `MCPRegistry` + `MCPToolSearch` | — | Done |
| Tool execution | ✅ `MCPClientManager.call_tool` | — | Done |
| JSON Schema | ✅ ToolDefinition.parameters | — | Done |

**Compliance: 100%**

### 2.6 Session/Context (Contract §6)

| Contract Requirement | JARVIS Current | Gap | Action |
|---------------------|----------------|-----|--------|
| Session lifecycle | ✅ fork/archive/delete | — | Done |
| Context window | ✅ `trim_conversation()` (recent > pinned > summary) | — | Done |
| Checkpointing | ✅ MemorySaverAdapter + **PostgresCheckpointer** (psycopg/asyncpg) | — | Done |
| Workspace awareness | ✅ `get_git_state()` + `get_file_tree()` | — | Done |

**Compliance: 100%** — PostgresCheckpointer added (psycopg/asyncpg)

### 2.7 Voice & Comms (Contract §7/§9 additions)

| Contract Requirement | JARVIS Current | Gap | Action |
|---------------------|----------------|-----|--------|
| Voice STT | ✅ faster-whisper `/stt` (`app/adapters/web/voice_routes.py`) | — | Done |
| Voice TTS | ✅ Edge TTS `/tts` + `/status` (`app/adapters/web/voice_routes.py`) | — | Done |
| Email read/search | ✅ `read_emails`, `search_emails` (SAFE) in `app/tools/comms_tools.py` | — | Done |
| Email send/reply | ✅ `send_email`, `reply_email` (SENSITIVE) via `app/integrations/email/` | — | Done |
| Morning brief | ✅ `BriefService` (`app/integrations/brief/`) + `get_brief` (SAFE) | — | Done |
| Push notifications | ✅ `PushService` (`app/integrations/push/`) + VAPID routes (`app/adapters/web/push_routes.py`) | — | Done |
| WhatsApp send | ✅ `send_message` via Cloud API (`app/integrations/whatsapp/`) | Receive path missing | Deviation (§5) |
| Telegram two-way | ✅ send + poller (`app/integrations/telegram/`, started from `app/main.py` lifespan) | — | Done |

**Compliance: 100%** (WhatsApp receive tracked as an approved deviation, not a gap)

---

## 3. Sprint-by-sprint Compliance Targets

### Sprint 0-2 (Weeks 0-4): Foundation + Hardening
- [x] CI pipeline (<!--fact:gate_count-->28<!--/fact--> gates, 9 contexts)
- [x] Security scanning (gitleaks, trufflehog, bandit, semgrep, trivy)
- [x] Containerization (Dockerfile + hadolint)
- [x] Release automation (auto-tag + publish)
- [x] 80%+ test coverage (94% achieved)
- [x] Conventional commits + pre-commit hooks

**Target Compliance**: 55% → **Achieved: 100%** (foundation items)

### Sprint 3 (Weeks 5-8): Capability Contract Alignment
- [x] Cognitive Engine — LangGraph orchestration (100%)
- [x] Memory — 4-stage pipeline + MemoryItem schema (100%)
- [x] MCP Client — stdio + Streamable HTTP (100%)
- [x] Session — MemorySaver + PostgresCheckpointer + fork/archive/delete (100%)
- [x] OTel — Spans with semantic conventions + OTLP exporter (100%)
- [x] Eval Suite — 10 evals + CI integration (100%)

**Target Compliance**: 90% → **Achieved: 100%**

### Sprint 4 (Weeks 9-12): Ecosystem Integration
- [x] PROFESSOR-J MCP server + mesh — 17 tools exposed
- [x] Cloudflare Pages deploy — auto-deploy on tag
- [x] Workspace awareness — git state + file tree
- [x] Memory pipeline façade — extract→manage→store→retrieve
- [x] Web app — FastAPI + chat UI + WebSocket streaming
- [x] Doc governance — still-checker, sync, progress bar
- [x] Versioning — git-derived, auto-tag, sync pyproject

**Target Compliance**: 100% → **Achieved: 100%**

---

## 4. Capability Contract Evolution Log

| Date | Contract Version | Change | JARVIS Action | Status |
|------|------------------|--------|---------------|--------|
| 2026-09-14 | 1.0.0 | Sprint 3 + 4 complete | All capabilities implemented | 🟢 100% |
| 2026-09-14 | 1.0.0 | +OTLP exporter, +embedding dedup, +PostgresCheckpointer | All gaps closed | 🟢 100% |

---

## 5. Deviation Register (Approved Exceptions)

| Capability | Deviation | Justification | Approved By | Expiry |
|------------|-----------|---------------|-------------|--------|
| WhatsApp receive (webhooks) | Not implemented — send-only | Meta requires a public HTTPS callback URL; Tailscale-only deployment has none (`app/integrations/whatsapp/` module docstring) | Architecture Review | Permanent |
| STEMMA Grounding | Not implemented | Explicitly out of contract | Architecture Review | Permanent |
| Ecosystem Dev Context | Not implemented | Unique to PROFESSOR-J | Architecture Review | Permanent |
| OTLP HTTP exporter | Implemented | Was optional, now done | Architecture Review | — |

---

## 6. Cross-Repo Sync Protocol

### 6.1 When PROFESSOR-J Adds Capability
1. PROFESSOR-J implements + proves
2. PROFESSOR-J creates PR against `docs/CAPABILITY-CONTRACT.md`
3. Contract PR approved → both repos schedule port
4. JARVIS implements → records in ADR → updates tracker

### 6.2 Breaking Changes
- Requires **major contract version** (v2.0.0)
- Coordinated rollout plan in both repos
- Migration window: 2 sprints minimum

---

## 7. Metrics Dashboard

| Metric | Current | Target | Source |
|--------|---------|--------|--------|
| Overall Compliance | 100% (manual roll-up, unmeasured by gate) | 100% | Tracker calculation (manual — no automated compliance gate exists) |
| Cognitive Engine | 100% | 100% | Sprint 3 + OTLP |
| Memory Subsystem | 100% | 100% | Sprint 3 + embedding dedup |
| Provider Routing | 100% | 100% | Done |
| Safety Gate | 100% | 100% | Done |
| MCP Client | 100% | 100% | Done |
| Session/Checkpoint | 100% | 100% | Sprint 4 + Postgres |
| Test Count | 1281 | — | pytest |
| Coverage | 94% | ≥ 80% | pytest --cov |

---

**Next Review**: 2026-12-14 (manual quarterly review)
**Owner**: Architecture Review Board
