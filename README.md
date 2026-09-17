# JARVIS

**Status**: ACTIVE
**Type**: guide
**Last Updated**: 2026-09-17
**Reviewed**: 2026-09-17
**Source**: `README.md` at HEAD

*A Rather Very Intelligent System.*

---

## SYSTEM ONLINE

```
█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█░░░░░░░░░░░░░██░░░░░██░░░░░░░░░░░░░░░░░░░░░░░░░
█░░░░░░░░░░░░░██░░░░░██░░░░░░░░░░░░░░░░░░░░░░░░░
█░░░░░░░░░░░░░██░░░░░██░░░░░░░░░░░░░░░░░░░░░░░░░
█░░░░░░░░░░░░░█████████░░░░░░░░░░░░░░░░░░░░░░░░░
█░░░░░░░░░░░░░░░░███░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

**Status:** OPERATIONAL  
**Version:** v3.22.1+dev  
**Uptime:** Continuous  
**Mode:** Personal AI Platform  

---

## OVERVIEW

JARVIS is a single-tenant AI platform built on a **Pragmatic Hybrid Architecture**: 
direct `async/await` for the hot path, an event bus for passive telemetry, and a 
**local automation plane (n8n)** that handles all scheduling, CI gating, and 
human-in-the-loop approvals.

**Endpoint:** `http://localhost:8000`  
**Interface:** FastAPI + Dark-mode SPA  
**Auth:** Bearer token (`JARVIS_API_KEY`)

---

## ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                     ADAPTERS (app/adapters/)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  REST HTTP   │  │  WebSocket  │  │  Bearer API Key Auth    │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  COMPOSITION ROOT (app/bootstrap.py)            │
│              ApplicationContainer + DEFAULT_TOOLSET              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   COGNITIVE BRAIN (app/brain/)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐ │
│  │ Intent   │→ │  Task    │→ │Execution │→ │   Response    │ │
│  │Analyzer  │  │ Planner  │  │ Runner   │  │ Synthesizer   │ │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
│  GUARDRAILS      │ │  MODEL POOL      │ │  MEMORY SUBSYSTEM    │
│ (app/guardrails/)│ │ (app/models/)    │ │ (app/memory/)        │
│                  │ │                  │ │                      │
│ @safety_gate     │ │ ModelRouter      │ │ MemoryService        │
│ SAFE/SENSITIVE/  │ │ Circuit Breakers │ │ ChromaDB + BM25      │
│ DESTRUCTIVE      │ │ Failover Chain   │ │ Hybrid Retrieval     │
└──────────────────┘ └──────────────────┘ └──────────────────────┘
```

---

## CAPABILITIES

### Cognitive Engine
- **Intent Analysis** — Classifies prompts: `DIRECT_CHAT`, `FILE_QUERY`, `TOOL_SEARCH`, `MULTI_STEP`
- **Task Planning** — Generates structured `ExecutionPlan` domain objects
- **Execution** — Runs plan steps against registered tools with safety policy enforcement
- **Response Synthesis** — Formats output with step-execution provenance

### Safety & Governance
- **Tiered Tool Policy** — `SAFE` (auto-pass), `SENSITIVE` (policy-checked), `DESTRUCTIVE` (mandatory approval)
- **HITL Gate** — Destructive steps pause for human approval via Slack/n8n
- **Approval Registry** — Tracks pending decisions, notifies once, auto-denies after 30 min

### Multi-Provider LLM Pool
- **Model Router** — Routes across OpenAI, Anthropic, Ollama, OpenRouter, etc.
- **Circuit Breakers** — 3-state (CLOSED/OPEN/HALF_OPEN) with automatic failover
- **Budget Tracking** — RPM/TPM limits per provider

### Hybrid Memory
- **Semantic Search** — ChromaDB vector similarity
- **Keyword Retrieval** — BM25 full-text search
- **Bi-Temporal** — Valid time + transaction time for fact management

### Automation Plane (n8n)
| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `JARVIS-CI-Local` | 30 min + manual | PR gating, commit statuses, Slack reports |
| `JARVIS-HITL` | 5 min + webhook | Approval polling, notifications, auto-deny |
| `JARVIS-Cleanup` | Weekly | Branch cleanup, stale PR closure |

### CI Gate (26 Checks)
```
SAST:       semgrep, bandit
SCA:        pip_audit, osv, trivy_fs
Secrets:    gitleaks, trufflehog
License:    licenses (copyleft policy)
Provenance: in-toto + cosign
Tests:      pytest, coverage (80% floor)
Lint:       ruff (ratcheted), mypy
Commits:    commitlint
Governance: 11 board checks
Build:      compileall, hadolint, docker_build
```

---

## QUICK START

```bash
# 1. Clone and enter
cd ~/Projects/JARVIS

# 2. Environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
echo "JARVIS_API_KEY=$(openssl rand -hex 32)" >> .env

# 4
# 4. Run
.venv/bin/python -m app.main

# 5. Verify
curl -s http://localhost:8000/api/v1/health -H "Authorization: Bearer $JARVIS_API_KEY"
```

**API Docs:** `http://localhost:8000/docs`  
**Web UI:** `http://localhost:8000`

---

## GOVERNANCE

| Check | Status |
|-------|--------|
| Import Layering | ✅ |
| Domain Purity | ✅ |
| Schema Drift | ✅ |
| Safety Gate Coverage | ✅ |
| MCP Tool Search | ✅ |
| OTEL Spans | ✅ |
| LangGraph Checkpoint | ✅ |
| Eval Suite | ✅ |
| Doc Drift | ✅ |
| Dependency Drift | ⚠️ (transitive deps) |

**ADRs:** 15 records (`docs/adr/ADR-001` → `ADR-015`)  
**Tracked Risks:** 16 entries in `docs/ACCEPTED_RISKS.md`

```bash
# Run governance suite
.venv/bin/python scripts/board/review.py
```

---

## DOCUMENTATION

| Document | Purpose |
|----------|---------|
| `docs/README.md` | Master navigation map |
| `docs/ARCHITECTURE.md` | Living topology and invariants |
| `docs/GOVERNANCE.md` | Decision authority and quality gates |
| `docs/API_CONTRACT.md` | REST/WS endpoints and auth |
| `docs/CI-GATE-SOTA.md` | Local CI engine details |
| `docs/ACCEPTED_RISKS.md` | Risk register |
| `docs/adr/` | Architecture Decision Records |

---

## LICENSE

ISC — see `LICENSE`

---

*End of line.*
