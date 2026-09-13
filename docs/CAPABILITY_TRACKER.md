# JARVIS Capability Contract Tracker

**Status**: ACTIVE
**Last Updated**: 2026-09-13

**Contract Version**: 1.0.0
**Contract Source**: `docs/CAPABILITY-CONTRACT.md`
**Review Cadence**: Quarterly (manual review — no `JARVIS-Capability-Sync`
workflow exists; see `docs/GOVERNANCE.md` §3)

---

## 1. Contract Compliance Overview

| Capability Area | Contract Requirement | JARVIS Current | PROFESSOR-J Reference | Compliance | Sprint Target |
|-----------------|---------------------|----------------|----------------------|------------|---------------|
| **Cognitive Engine** | LangGraph orchestration | Direct async loop | ADR-003, PR #75 | 🟡 **30%** | Sprint 3 |
| **Memory Subsystem** | 4-stage pipeline + rich schema | Hybrid BM25+Chroma | PR #75 | 🟡 **45%** | Sprint 3 |
| **Provider Routing** | Multi-provider + circuit breakers | ✅ Implemented | ✅ Implemented | ✅ **100%** | Done |
| **Safety Gate (HITL)** | Tiered + DESTRUCTIVE blocks | ✅ Implemented | ✅ Implemented | ✅ **100%** | Done |
| **MCP Client** | stdio + Streamable HTTP | ❌ None | PR #86 | 🔴 **0%** | Sprint 3 |
| **Voice I/O** | Piper + faster-whisper | 🔵 Out of scope | ✅ Implemented | N/A | N/A |
| **Session/Checkpoint** | LangGraph MemorySaver | Basic file-backed | ✅ Implemented | 🟡 **60%** | Sprint 3 |
| **STEMMA Grounding** | LHS Adapter | 🔵 Out of scope | ✅ Implemented | N/A | N/A |
| **Ecosystem Dev Context** | Skills, MCPs, governance | 🔵 Out of scope | ✅ Unique to PROFESSOR-J | N/A | N/A |

**Overall Compliance**: **~48%** (5/10 capabilities at ≥60%)

---

## 2. Detailed Capability Tracking

### 2.1 Cognitive Engine (Contract §1)

| Contract Requirement | JARVIS Current | Gap | Action | Sprint |
|---------------------|----------------|-----|--------|--------|
| LangGraph-based orchestration | Direct async loop (IntentAnalyzer→TaskPlanner→ExecutionRunner→ResponseSynthesizer) | **Architecture mismatch** | Port PROFESSOR-J LangGraph engine; replace `app/brain/` | 3 |
| Typed `CognitiveState` | Implicit in plan/execution | No explicit state type | Define `CognitiveState` TypedDict | 3 |
| Required nodes: intent_analyzer, task_planner, tool_executor, response_synthesizer, evaluator | Has first 4, no evaluator | Missing evaluator node | Add evaluator node (quality gate) | 3 |
| Control flow with `interrupt()` for HITL | Uses `@safety_gate` → HITLRequestEvent + pause | Different mechanism | Align to `interrupt()`/`Command(resume=...)` | 3 |
| Streaming: `stream_mode="values"` + `stream_mode="updates"` | SSE/WS custom streaming | Protocol mismatch | Implement LangGraph streaming | 3 |
| OTel spans with semantic conventions | InMemoryAsyncBus telemetry only | No OTel export | Add OTel exporter to Langfuse | 3 |

### 2.2 Memory Subsystem (Contract §2)

| Contract Requirement | JARVIS Current | Gap | Action | Sprint |
|---------------------|----------------|-----|--------|--------|
| 4-stage pipeline: extract→manage→store→retrieve | Hybrid retriever + MemoryService | Missing extract + manage stages | Add `FactExtractor` + `MemoryManager` pipeline | 3 |
| `MemoryItem` schema (fact/episode/procedure/preference/conversation) | Basic `MemoryRecord` | Schema too simple | Implement full `MemoryItem` with all fields | 3 |
| Scope: session/user/global | No scope concept | Missing scope | Add `scope` field to memory | 3 |
| Dense retrieval (embeddings) + sparse (BM25) | ✅ Hybrid retriever | ✅ Implemented | — | Done |
| Hybrid ranker (0.6 dense + 0.4 sparse configurable) | Basic hybrid | Weights not configurable | Make weights configurable | 3 |
| Time-decay + confidence weighting | No | Missing | Add decay + confidence to ranker | 3 |
| Fact extraction via LLM | Basic extractor | Not LLM-based | Port PROFESSOR-J LLM extractor | 3 |
| Near-duplicate deduplication | No | Missing | Add embedding-based deduplication | 3 |
| Provenance tracking (source, confidence, draft_status, lhs_entity_ids) | No | Missing | Add all provenance fields | 3 |

### 2.3 Provider Routing (Contract §3)

| Contract Requirement | JARVIS Current | Gap | Action | Sprint |
|---------------------|----------------|-----|--------|--------|
| Multi-provider (≥3) | ✅ 4 providers | — | — | Done |
| Circuit breaker per provider | ✅ ResourceManager | — | — | Done |
| Task routing (chat/reasoning/code/embedding/structured) | ✅ TaskType enum | — | — | Done |
| Structured output (JSON schema/Pydantic) | Partial (some clients) | Not all clients | Ensure all clients support structured output | 1 |
| Cost tracking (token in/out, budgets) | ✅ TokenBudgetManager | — | — | Done |

### 2.4 Safety Gate (Contract §4)

| Contract Requirement | JARVIS Current | Gap | Action | Sprint |
|---------------------|----------------|-----|--------|--------|
| Tiered: READ/WRITE/DESTRUCTIVE | SAFE/SENSITIVE/DESTRUCTIVE | Terminology diff | Align terminology | 1 |
| DESTRUCTIVE blocks without HITL | ✅ @safety_gate | — | — | Done |
| HITL is blocking, no auto-continue | ✅ Pauses execution | — | — | Done |
| Audit log on every gate evaluation | InMemoryAsyncBus events | Not persisted | Add persistent audit log | 2 |

### 2.5 Tool/MCP Contract (Contract §5)

| Contract Requirement | JARVIS Current | Gap | Action | Sprint |
|---------------------|----------------|-----|--------|--------|
| stdio MCP | ❌ None | Missing | Port from PROFESSOR-J PR #86 | 3 |
| Streamable HTTP MCP | ❌ None | Missing | Port from PROFESSOR-J PR #86 | 3 |
| Tool registry (discover, list, search) | DocumentationAgent only (7 tools) | Limited scope | Build general tool registry | 3 |
| Tool execution via ToolExecutor + safety gate | ✅ DocumentationAgent | Not general | Generalize ToolExecutor | 3 |
| JSON Schema for args/returns | ✅ ToolDefinition.parameters | — | — | Done |

### 2.6 Session/Context (Contract §6)

| Contract Requirement | JARVIS Current | Gap | Action | Sprint |
|---------------------|----------------|-----|--------|--------|
| Session lifecycle (create/resume/fork/archive/delete) | Basic SessionManager | Missing fork/archive | Extend SessionManager | 3 |
| Token-aware context trimming | ContextWindowManager | Priority logic basic | Implement priority trimming (recent > pinned > summary) | 3 |
| Checkpointing (MemorySaver/PostgresCheckpointer) | File-backed JSON | Not LangGraph compatible | Add LangGraph checkpointers | 3 |
| Workspace awareness (cwd, git, file tree) | WorkspaceManager | Basic | Enhance with git state | 3 |

---

## 3. Sprint-by-Sprint Compliance Targets

### Sprint 0-1 (Weeks 0-2): Foundation
- [ ] Fix terminology: SAFE/SENSITIVE/DESTRUCTIVE → READ/WRITE/DESTRUCTIVE
- [ ] Structured output for all providers
- [ ] Persistent audit log for safety gate
- [ ] Provider cost tracking verified

**Target Compliance**: 55%

### Sprint 2 (Weeks 3-4): Hardening
- [ ] Memory scope field added
- [ ] Hybrid ranker weights configurable
- [ ] Session fork/archive implemented
- [ ] Context trimming priority logic enhanced

**Target Compliance**: 65%

### Sprint 3 (Weeks 5-8): Capability Contract Alignment
- [ ] **Cognitive Engine**: Port LangGraph orchestration from PROFESSOR-J
- [ ] **Memory**: Full 4-stage pipeline with `MemoryItem` schema
- [ ] **MCP Client**: stdio + Streamable HTTP
- [ ] **Session**: LangGraph checkpointers (MemorySaver/Postgres)
- [ ] **OTel**: Spans with semantic conventions
- [ ] **Eval Suite**: Regression suite for model behavior

**Target Compliance**: 90%

### Sprint 4 (Weeks 9-12): Ecosystem Integration
- [ ] STEMMA LHS adapter
- [ ] LearningHub SSO integration
- [ ] PROFESSOR-J MCP server
- [ ] Contract version bump if needed

**Target Compliance**: 100% (v1.0 complete)

---

## 4. Capability Contract Evolution Log

| Date | Contract Version | Change | JARVIS Action | Status |
|------|------------------|--------|---------------|--------|
| 2026-09-10 | 1.0.0 | Initial contract established | Baseline assessment | 🔴 48% |

---

## 5. Compliance Verification (manual quarterly review)

> No `JARVIS-Capability-Sync` n8n workflow exists. This section describes the
> checks a reviewer runs by hand; the code block below is an illustration of the
> checks, not a deployed workflow.

### 5.1 Automated Checks (Run Quarterly)

```python
# checks/capability_contract_check.py
def verify_contract_compliance():
    checks = {
        "cognitive_engine_langgraph": check_langgraph_orchestration(),
        "memory_4_stage_pipeline": check_memory_pipeline_stages(),
        "memory_item_schema": check_memory_item_schema(),
        "mcp_client_stdio": check_mcp_stdio(),
        "mcp_client_http": check_mcp_http(),
        "session_checkpointer": check_langgraph_checkpointer(),
        "otel_spans": check_otel_semantic_conventions(),
        "eval_suite_exists": check_eval_suite(),
    }
    return all(checks.values())
```

### 5.2 Manual Review Checklist (Quarterly)

- [ ] Compare `docs/CAPABILITY-CONTRACT.md` with PROFESSOR-J implementation
- [ ] Verify all new capabilities in PROFESSOR-J have tracker entries
- [ ] Review contract version for breaking changes
- [ ] Update sprint targets based on PROFESSOR-J roadmap
- [ ] Document any deliberate deviations with justification

---

## 6. Deviation Register (Approved Exceptions)

| Capability | Deviation | Justification | Approved By | Expiry |
|------------|-----------|---------------|-------------|--------|
| Voice I/O | Not implemented | Explicitly out of contract for JARVIS | Architecture Review | Permanent |
| STEMMA Grounding | Not implemented | Explicitly out of contract for JARVIS | Architecture Review | Permanent |
| Ecosystem Dev Context | Not implemented | Unique to PROFESSOR-J | Architecture Review | Permanent |

---

## 7. Cross-Repo Sync Protocol

### 7.1 When PROFESSOR-J Adds Capability

1. PROFESSOR-J implements + proves (tests, docs, production)
2. PROFESSOR-J creates PR against `docs/CAPABILITY-CONTRACT.md` with interface
3. Contract PR approved → both repos schedule port in next sprint
4. JARVIS implements → records in ADR → updates this tracker

### 7.2 When JARVIS Adds Capability

1. JARVIS implements + proves
2. JARVIS creates PR against `docs/CAPABILITY-CONTRACT.md`
3. Contract PR approved → PROFESSOR-J schedules port
4. PROFESSOR-J implements → records in ADR

### 7.3 Breaking Changes

- Requires **major contract version** (v2.0.0)
- Coordinated rollout plan in both repos
- Migration window: 2 sprints minimum
- Both repos must approve before merge

---

## 8. Metrics Dashboard (n8n)

| Metric | Current | Target | Source |
|--------|---------|--------|--------|
| Overall Compliance | 48% | 100% | Tracker calculation |
| Cognitive Engine | 30% | 100% | Sprint 3 |
| Memory Subsystem | 45% | 100% | Sprint 3 |
| Provider Routing | 100% | 100% | Done |
| Safety Gate | 100% | 100% | Done |
| MCP Client | 0% | 100% | Sprint 3 |
| Session/Checkpoint | 60% | 100% | Sprint 3 |

---

## 9. Related Documents

| Document | Purpose |
|----------|---------|
| `docs/CAPABILITY-CONTRACT.md` | Source contract |
| `docs/ARCHITECTURE.md` | Current implementation |
| `docs/ROADMAP.md` | Sprint plans |
| `docs/adr/ADR-003` | LangGraph orchestration (PROFESSOR-J) |
| `docs/adr/ADR-004` | Memory subsystem |
| `docs/adr/ADR-008` | Safety gate policy |

---

**Next Review**: 2026-12-10 (manual quarterly review)
**Owner**: Architecture Review Board
**Escalation**: If compliance < 70% at Sprint 3 end → P2 incident
