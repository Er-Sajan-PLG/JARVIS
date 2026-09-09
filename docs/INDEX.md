# JARVIS Documentation Index — Living Document v3.0.0

**Status**: COMPLETE — All fundamental documents created  
**Last Updated**: 2026-09-10  
**Source**: Forensic Architecture Audit + USAT Audit + Capability Contract v1.0

---

## 📚 Fundamental Documents (Read in Order)

| # | Document | Purpose | Start Here? |
|---|----------|---------|-------------|
| 1 | **[ARCHITECTURE.md](ARCHITECTURE.md)** | Living system topology, cognitive engine loop, package boundaries, n8n integration | ✅ **YES** |
| 2 | **[GOVERNANCE.md](GOVERNANCE.md)** | Decision authority, branching model, n8n workflow governance, quality gates, security, release process | ✅ **YES** |
| 3 | **[ROADMAP.md](ROADMAP.md)** | Prioritized sprint plan (Sprint 0-4), technical debt register, milestones, success metrics | ✅ **YES** |
| 4 | **[DEVELOPMENT.md](DEVELOPMENT.md)** | Daily workflow, local setup, testing standards, code standards, git workflow, debugging | 🔄 Reference |
| 5 | **[API_CONTRACT.md](API_CONTRACT.md)** | REST/WS endpoints, auth, data models, error codes, n8n integration patterns | 🔄 Reference |
| 6 | **[CAPABILITY_TRACKER.md](CAPABILITY_TRACKER.md)** | Capability Contract v1.0 compliance tracking (JARVIS ↔ PROFESSOR-J) | 📊 Tracking |

---

## 🚀 Quick Start (Sprint 0)

```bash
cd /home/sajan/Projects/JARVIS

# 1. Recreate venv with Python 3.11/3.12
python3.11 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add missing API key
grep -q JARVIS_API_KEY .env || echo "JARVIS_API_KEY=$(openssl rand -hex 32)" >> .env

# 4. Archive legacy servers (dead code)
mkdir -p app/legacy
mv app/api/server.py app/web_api_server.py app/legacy/

# 5. Fix WebSocket auth (add validate_api_key to ws_router)
# Edit: app/adapters/websocket/stream.py

# 6. Verify v3.0 works
python -m app.main

# 7. Health check
curl -H "Authorization: Bearer $JARVIS_API_KEY" http://localhost:8000/api/v1/health
```

**Expected**: Server starts, health returns 200, chat completion works via REST + WS

---

## 🎯 Current State Summary (Forensic Audit)

| Aspect | Status | Evidence |
|--------|--------|----------|
| **v3.0 Architecture** | ✅ Implemented | `app/main.py`, `app/bootstrap.py` import cleanly |
| **Legacy v2.x** | 🗑️ Dead code | `app/api/server.py`, `app/web_api_server.py` crash on import |
| **Venv** | ❌ Empty | 0 packages installed |
| **JARVIS_API_KEY** | ❌ Missing | Not in `.env` |
| **CI/CD** | ❌ None | Only Jules conflict resolver workflow |
| **Python Version** | ⚠️ 3.14 (broken) | Must use 3.11/3.12 |
| **Capability Contract** | ~48% | 5/10 capabilities at ≥60% |

---

## 🔑 Key Architectural Decisions (Frozen)

1. **v3.0 is canonical** — Archive legacy servers, don't migrate
2. **n8n owns ALL automation** — No GitHub Actions for business logic
3. **Python 3.11/3.12 only** — 3.14 breaks ML deps (chromadb, sentence-transformers, pydantic)
4. **Capability Contract drives features** — JARVIS must match PROFESSOR-J interface
5. **Direct async cognitive loop** — No event bus in data path (telemetry only)
6. **Single-tenant Bearer auth** — `JARVIS_API_KEY` required for all endpoints

---

## 📋 Document Relationships

```
ARCHITECTURE.md (System Topology)
    │
    ├─→ GOVERNANCE.md (How we decide/enforce)
    │       │
    │       └─→ ROADMAP.md (What we build when)
    │               │
    │               ├─→ DEVELOPMENT.md (How we build daily)
    │               │
    │               ├─→ API_CONTRACT.md (What we expose)
    │               │
    │               └─→ CAPABILITY_TRACKER.md (Contract compliance)
    │
    └─→ docs/adr/ (Architectural Decision Records)
```

---

## 🔄 Document Maintenance Rules

| Rule | Enforcement |
|------|-------------|
| **Updated in same PR as code** | PR template requires docs checkbox |
| **Living documents** | Version in header; no separate version file |
| **Source of truth = repo state** | Forensic audit > documentation |
| **n8n workflow changes** | Exported JSON committed to `n8n/workflows/` |
| **Capability Contract changes** | Requires coordinated rollout with PROFESSOR-J |

---

## 📅 Review Cadence

| Document | Review Frequency | Trigger |
|----------|------------------|---------|
| ARCHITECTURE.md | Quarterly | Architectural change |
| GOVERNANCE.md | Quarterly | Process change |
| ROADMAP.md | Sprint planning | Sprint boundary |
| DEVELOPMENT.md | As needed | Tooling change |
| API_CONTRACT.md | Per release | API change |
| CAPABILITY_TRACKER.md | Quarterly | n8n `JARVIS-Capability-Sync` |

---

## 🔗 Cross-References

| From | To | Link Type |
|------|-----|-----------|
| ARCHITECTURE.md | GOVERNANCE.md | Authority |
| GOVERNANCE.md | ROADMAP.md | Execution |
| ROADMAP.md | DEVELOPMENT.md | Workflow |
| DEVELOPMENT.md | API_CONTRACT.md | Implementation |
| CAPABILITY_TRACKER.md | CAPABILITY-CONTRACT.md | Compliance |
| All | docs/adr/ | Decisions |

---

## 📝 Next Actions (Immediate)

1. **Execute Sprint 0** (above) — unblocks everything
2. **Commit these 6 documents** — freeze current governance
3. **Create n8n workflows** — `JARVIS-Setup-Env`, `JARVIS-CI`, `JARVIS-Deploy`
4. **Run first USAT audit post-fix** — verify hygiene improvement
5. **Sync with PROFESSOR-J** — Capability Contract alignment kickoff

---

**Document Owner**: Architecture Review Board  
**Next Full Review**: 2026-12-10  
**Emergency Override**: P0 incident → immediate update required