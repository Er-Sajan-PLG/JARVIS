# CAPABILITY CONTRACT — JARVIS ↔ PROFESSOR-J Shared AI Capability Surface

**Version:** 1.0.0
**Status:** Contract definition (not code). Both repos implement to this contract.
**Authority:** JARVIS repository governance. Per-repo governance overrides implementation detail; contract interface is binding.
**Related:** `docs/ARCHITECTURE.md` (JARVIS system topology),
`docs/CAPABILITY_TRACKER.md` (compliance tracking),
`docs/adr/ADR-013-jarvis-orchestrates-n8n-executes.md` (orchestration authority)

> **Note (2026-09-12):** this header previously cited
> `docs/ECOSYSTEM-TARGET-ARCHITECTURE.md`, which does not exist in this
> repository. The reference was removed rather than left dangling.

---

## Purpose

PROFESSOR-J and JARVIS must have "the same capability" without sharing code (repository invariant: no package-level coupling, no shared platform services). This contract defines **what must be present in both systems** at the interface level. Each repo implements it in its own codebase; patterns are ported, not imported.

The contract is versioned. Breaking changes require a new contract version and explicit migration planning in both repos.

---

## 1. Cognitive Engine Contract (the orchestration loop)

Both systems MUST provide a LangGraph-based orchestration runtime with the following typed state and node contract.

### 1.1 Cognitive State (the single source of truth)

```python
# Canonical shape (both repos implement equivalent)
class CognitiveState(TypedDict):
    # Immutable per-turn
    session_id: str
    turn_id: int
    user_input: str
    # Mutable during turn
    intent: Optional[IntentAnalysis]
    plan: Optional[TaskPlan]
    execution_results: List[ToolResult]
    synthesized_response: Optional[str]
    # Safety / provenance
    safety_flags: List[SafetyFlag]
    provenance: List[ProvenanceRecord]  # critical for PROFESSOR-J grounding
    # Control
    next_node: Literal["intent", "plan", "execute", "synthesize", "interrupt", "end"]
    metadata: Dict[str, Any]
```

### 1.2 Required Nodes (exact names may differ; functional contract is binding)

| Node | Input keys | Output keys | Responsibility |
|------|------------|-------------|----------------|
| `intent_analyzer` | `user_input`, `provenance` | `intent`, `safety_flags` | Classify intent; extract entities; emit safety flags for DESTRUCTIVE intents |
| `task_planner` | `intent`, `memory_context` | `plan` | Decompose into ordered tool calls / sub-tasks |
| `tool_executor` | `plan.steps`, `safety_flags` | `execution_results` | Execute tools behind `@safety_gate`; **HITL required for DESTRUCTIVE** |
| `response_synthesizer` | `execution_results`, `intent`, `provenance` | `synthesized_response` | Compose final answer; **PROFESSOR-J: cite LHS ids + draft status** |
| `evaluator` (optional) | `synthesized_response`, `intent` | `quality_score`, `repair_orders` | Gate before output (PROFESSOR-J has this; JARVIS may port) |

### 1.3 Control flow

```
intent_analyzer → task_planner → tool_executor → response_synthesizer → [evaluator] → end
                         ↑              │
                         └──── interrupt (HITL) ────┘
```

- `interrupt()` on DESTRUCTIVE tool calls is mandatory. `Command(resume=...)` for resume.
- Streaming: token streaming (`stream_mode="values"`) + node updates (`stream_mode="updates"`).

### 1.4 Observability contract

- Every node execution emits an OTel span with semantic conventions: `gen_ai.agent.name`, `gen_ai.tool.name`, `gen_ai.guardrail.result`.
- Exporters: OTLP HTTP to Langfuse (or equivalent). Both repos must be able to turn this on.
- Event bus (if present) is **telemetry only** — never the data path for state.

---

## 2. Memory Subsystem Contract

Both systems MUST provide a four-stage memory pipeline:

```
extract → manage → store → retrieve
```

### 2.1 Memory Schema (both repos support)

```python
class MemoryItem(BaseModel):
    id: str
    content: str
    kind: Literal["fact", "episode", "procedure", "preference", "conversation"]
    scope: Literal["session", "user", "global"]  # JARVIS uses all; PROFESSOR-J: user/global
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    # Retrieval hints
    embedding: Optional[List[float]] = None  # dense (optional leg)
    keywords: List[str] = []                 # sparse (always present)
    # Provenance (PROFESSOR-J requirement)
    source: Literal["user", "stemma", "web", "tool", "inferred"] = "user"
    confidence: float = 1.0
    draft_status: Literal["canonical", "draft", "deprecated"] = "canonical"
    lhs_entity_ids: List[str] = []           # e.g., ["lhs:phys.force"]
```

### 2.2 Retrieval Contract

Both systems MUST support:
- Sparse retrieval (BM25 / keyword) — always available
- Dense retrieval (embeddings) — behind a feature flag / optional leg
- Hybrid ranker (weighted composite: `0.6 * dense + 0.4 * sparse` configurable)
- Time-decay + confidence weighting
- `retrieve(query, top_k, filters)` → `List[MemoryItem]` with scores

### 2.3 Fact Extraction Contract

- LLM-based extractor (or rule-based) runs on conversation turns
- Produces `MemoryItem(kind="fact")` candidates
- Deduplication via near-duplicate detection (embedding or string similarity)
- PROFESSOR-J: extracted STEM facts → `canonical-review-signal` (not auto-canonical)

---

## 3. LLM Provider Routing Contract

Both systems MUST provide:

```python
class ProviderCatalog:
    # Curated defaults + dynamic discovery
    def get_model(self, task: ModelTask) -> ModelHandle:
        """Returns a handle with circuit breaker, retry, timeout."""
    def list_available(self) -> List[ModelSpec]:
        ...
```

| Requirement | Detail |
|-------------|--------|
| Multi-provider | At least 3 providers configurable (e.g., OpenAI, Anthropic, Ollama/local) |
| Circuit breaker | Per-provider; trip on 5xx / timeout; exponential backoff |
| Task routing | `chat`, `reasoning`, `code`, `embedding`, `structured_output` |
| Structured output | Must support JSON schema / Pydantic model coercion |
| Cost tracking | Token in/out per call; budget caps per session / turn |

---

## 4. Safety Gate Contract (repository invariant)

**This is the single non-negotiable boundary:**

```
SafetyPolicy → ToolExecutor → @safety_gate(tier=DESTRUCTIVE) → HITL
```

Both systems MUST implement:
- Tiered tool classification: `READ` / `WRITE` / `DESTRUCTIVE`
- `DESTRUCTIVE` tools **must not execute** without explicit human confirmation
- The gate is a **runtime wrapper**, not a policy document — it intercepts and blocks
- HITL is blocking; agent cannot auto-continue or auto-approve
- Audit log entry on every gate evaluation (allow/deny, reason, human decision)

---

## 5. Tool / MCP Contract

| Capability | Detail |
|------------|--------|
| stdio MCP | Spawn + manage stdio MCP servers |
| Streamable HTTP MCP | Connect to remote MCP endpoints |
| Tool registry | Discover, list, search tools by name/description |
| Tool execution | Through `ToolExecutor` behind safety gate |
| Tool schema | JSON Schema for args + returns; strict validation |

---

## 6. Session / Context Management Contract

| Requirement | Detail |
|-------------|--------|
| Session lifecycle | create / resume / fork / archive / delete |
| Context window | Token-aware trimming with priority (recent > pinned > summary) |
| Checkpointing | LangGraph `MemorySaver` (dev) / `PostgresCheckpointer` (prod) |
| Workspace awareness | Current working directory + git state + file tree (configurable depth) |

---

## 7. What is EXPLICITLY OUT OF CONTRACT (not required to match)

| Concern | JARVIS | PROFESSOR-J |
|---------|--------|-------------|
| Personal data / user-owned files | Full access | No |
| Web search / research agents | Yes (general) | Restricted to STEMMA-grounded paths |
| Voice I/O | Optional | Yes (Piper + faster-whisper) |
| Frontend framework | TBD (Next.js / desktop) | Next.js 15 web |
| Learning-specific agents | No | ProfessorAgent, ResearchAgent, EvaluatorAgent |
| Curriculum / grade awareness | No | Yes (via LHS adapter) |
| Ecosystem development context (skills, MCPs, tools, governance) | No | **Yes (unique to PROFESSOR-J)** — full workspace dev context so it can develop the ecosystem |

---

## 8. Evolution Rules

1. Contract version in `docs/CAPABILITY-CONTRACT.md` header.
2. Minor additions (new optional fields, new non-breaking nodes) → patch version. Both repos implement within same cycle.
3. Breaking changes (node removed, state shape changed, safety gate signature changed) → major version. Requires coordinated rollout + migration plan in both repos.
4. Each repo records its implementation conformance in its own ADR (e.g., "ADR-X: Implement Capability Contract v1.0").
5. The contract is the single source for "same capability" — not code equality.

---

## 9. Current Implementation Status (as of this contract)

| Capability | PROFESSOR-J | JARVIS |
|------------|-------------|--------|
| Cognitive Engine (LangGraph) | ✅ ADR-003 | ❌ to port |
| Memory (rich schema, hybrid) | ✅ PR #75 | ❌ to port |
| Provider Routing | ✅ | ✅ (JARVIS has this) |
| Safety Gate (HITL) | ✅ | ✅ (JARVIS has this) |
| MCP Client | ✅ PR #86 | ❌ to port |
| Voice | ✅ | ❌ not in JARVIS |
| STEMMA Grounding (LHS Adapter) | ✅ | N/A (explicitly out of scope) |
| Ecosystem Development Context (skills, MCPs, tools, governance) | ✅ (unique) | N/A (JARVIS doesn't need this) |
| Session/Checkpoint | ✅ | ✅ |

This table is the **baseline for "no double work"**: every ✅ in PROFESSOR-J that is ❌ in JARVIS is a pattern-port task for JARVIS. Every ✅ in JARVIS that is ❌ in PROFESSOR-J is either out of contract or a future port.

---

## 10. How a new capability enters the contract

1. **Design in one repo** (e.g., PROFESSOR-J builds a new evaluator agent).
2. **Prove it** (tests, docs, production usage).
3. **Extract the interface** (state keys, node I/O, config schema) into a PR against this contract.
4. **Contract PR approved** → both repos schedule the port in their next phase.
5. **Both repos implement** → record in each repo's ADR.

No capability enters the contract by fiat; it must be proven in at least one repo first.
