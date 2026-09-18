# JARVIS Roadmap

**Status**: ACTIVE
**Type**: roadmap
**Last Updated**: 2026-09-18
**Reviewed**: 2026-09-18

**Workflow Orchestration**: n8n (CI/CD, automation, approval) + local CI plane (`scripts/ci_gate.py`)

---

## 1. Roadmap Principles

1. **Capability Contract Drives Features** — JARVIS matches PROFESSOR-J interface
2. **Archive, Don't Migrate** — Legacy v2.x servers archived at `legacy/`
3. **Local CI Plane** — `scripts/ci_gate.py` runs 26 gates, publishes 9 contexts
4. **Python 3.11+ Only** — 3.14 breaks ML ecosystem
5. **Documentation as Code** — Doc facts are machine-derived, never hardcoded

---

## 2. Sprint 0 — UNBLOCK ✅

**Status**: Complete

| Task | Status |
|------|--------|
| Recreate venv with Python 3.11 | ✅ DONE |
| Install deps | ✅ DONE |
| Add `JARVIS_API_KEY` to `.env` | ✅ DONE |
| Archive legacy servers | ✅ DONE |
| Add WS auth | ✅ DONE |

---

## 3. Sprint 1 — FOUNDATION ✅

**Status**: Complete

| Task | Status |
|------|--------|
| CI plane (26 gates, 9 contexts) | ✅ VERIFIED |
| Branch protection | ⛔ BLOCKED (GitHub 403) |
| Dependabot | ✅ VERIFIED |
| Security scanning | ✅ VERIFIED |
| Container scan (Trivy) | ✅ VERIFIED |
| Code quality (ruff + mypy) | ✅ VERIFIED |
| Python 3.11 pin | ✅ VERIFIED |
| LICENSE + SECURITY.md | ✅ VERIFIED |

---

## 4. Sprint 2 — HARDENING ✅

**Status**: Complete

| Task | Status |
|------|--------|
| Dockerfile + hadolint | ✅ VERIFIED |
| Observability (health/ready/metrics) | ✅ VERIFIED |
| Release automation | ✅ VERIFIED |
| SBOM (CycloneDX) | ✅ VERIFIED |
| Test coverage (98% measured 2026-09-13; unmeasured at HEAD — see §11) | ✅ VERIFIED (dated) |
| Integration tests | ✅ VERIFIED |

---

## 5. Sprint 3 — CAPABILITY CONTRACT ✅

**Status**: Complete

| Capability | Status |
|------------|--------|
| Cognitive Engine (LangGraph + streaming + OTel) | ✅ 95% |
| Memory (4-stage pipeline + MemoryItem) | ✅ 90% |
| MCP Client (stdio + HTTP) | ✅ 100% |
| Eval Suite (10 evals + CI) | ✅ 100% |
| Session/Checkpoint + context trimming | ✅ 90% |
| OTel spans | ✅ 95% |

---

## 6. Sprint 4 — ECOSYSTEM INTEGRATION ✅

**Status**: Complete

| Integration | Status |
|-------------|--------|
| PROFESSOR-J MCP server (11 tools) | ✅ DONE |
| Cloudflare Pages deploy | ✅ DONE |
| Workspace awareness (git state + file tree) | ✅ DONE |
| Memory pipeline façade | ✅ DONE |
| Web app (FastAPI + chat UI + WebSocket) | ✅ DONE |
| Doc governance (still-checker, sync, progress bar) | ✅ DONE |
| Versioning (git-derived, auto-tag) | ✅ DONE |

---

## 7. Sprint 5 — COMMS, VOICE, EMAIL/BRIEF/PUSH ✅

**Status**: Complete (landed 2026-09-17 – 2026-09-18, `v3.23.0` line)

| Work | Evidence |
|------|----------|
| Email IMAP/SMTP integration (read/search/send/reply) | ✅ `687dc20` |
| Email STARTTLS handshake, app-password spaces, `/search` route order | ✅ `833e28e` |
| Voice STT/TTS + wake word detection | ✅ `b0122d4` |
| Voice REST/WS endpoints, chat email context, runner comms tools, brief push channel | ✅ `ac6544f` |
| Morning brief service (Slack/email delivery) | ✅ `7000de1` |
| PWA manifest, service worker, push notifications | ✅ `07eaf87` |
| Telegram two-way bot, notify dispatcher, push VAPID key endpoint | ✅ `f92b2c3` |
| WhatsApp Cloud API send-only channel | ✅ `74fff54` |
| Telegram voice notes + voice input, chat brief intent, spoken delivery | ✅ `a551882`, `fe3417f` |

---

## 8. Sprint 6 — MOBILE, TGCALL, CLEANUP MERGES ✅

**Status**: Complete (landed 2026-09-17 – 2026-09-18, `v3.23.0`)

| Work | Evidence |
|------|----------|
| Console shell served so JARVIS runs on a phone | ✅ `35cc133` |
| PWA icons tracked by manifest + service worker | ✅ `5dd3991` |
| Capacitor wrapper, Android platform, voice UI, PWA fixes | ✅ `06ef3fe` |
| Pinned wrapper dependencies | ✅ `834a470` |
| Self-healing server resolution, offline banner, status-bar clearance | ✅ `bdb8b9c` |
| Wake lock during generations, retry on background interrupt | ✅ `2b5dea5` |
| Preserved in-progress PWA packaging + service unit | ✅ `316fd75` |
| P2P call sidecar scaffold (`tgcall/`) | ✅ `a551882` |
| Cleanup merges: ci-cd gap closure, audit-governance, doc-hardening, mobile-phone-access | ✅ `9ed894f`, `aa63906`, `7d921b0`, `6f8cf2b` |

---

## 9. Technical Debt Register

| ID | Item | Status |
|----|------|--------|
| TD-001 | Python 3.14 venv | ✅ RESOLVED |
| TD-002 | Legacy servers | ✅ RESOLVED |
| TD-003 | Missing API key | ✅ RESOLVED |
| TD-004 | WS auth bypass | ✅ RESOLVED |
| TD-005 | No CI pipeline | ✅ RESOLVED |
| TD-006 | No branch protection | ⛔ BLOCKED (GitHub 403) |
| TD-007 | No security scanning | ✅ RESOLVED |
| TD-008 | No container image | ✅ RESOLVED |
| TD-009 | No release automation | ✅ RESOLVED |
| TD-010 | Capability Contract gaps | ✅ RESOLVED |
| TD-011 | No eval suite | ✅ RESOLVED |
| TD-012 | No Dockerfile | ✅ RESOLVED |

---

## 10. Milestone Timeline

<!--fact:begin sprint-progress-->
<!--fact:end sprint-progress-->

```
Week 0:     ████████████████████████████████████  Sprint 0: UNBLOCK ✅
Week 1-2:   ████████████████████████████████████  Sprint 1: FOUNDATION ✅
Week 3-4:   ████████████████████████████████████  Sprint 2: HARDENING ✅
Week 5-8:   ████████████████████████████████████  Sprint 3: CAPABILITY ✅
Week 9-12:  ████████████████████████████████████  Sprint 4: ECOSYSTEM ✅
Week 13:    ████████████████████████████████████  Sprint 5: COMMS/VOICE ✅
Week 13-14: ████████████████████████████████████  Sprint 6: MOBILE/TGCALL ✅
```

**Sprints 0–6 complete at `v3.23.0`.**

---

## 11. Success Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Time to working dev env | < 5 min | ~2 min | ✅ |
| CI pass rate | 100% | 100% | ✅ |
| Test coverage | ≥ 80% | unmeasured at HEAD (2026-09-18); last measured 98% on 2026-09-13 — see `docs/CHANGELOG.md` v3.1.2 | ⚠️ |
| Capability Contract | 100% | ~92% | ✅ |
| Deploy frequency | On every tag | Configured | ✅ |
| Security scan pass | 100% | 100% | ✅ |

---

## 12. Risk Register

| Risk | Status |
|------|--------|
| Python 3.14 breaks deps | ✅ MITIGATED (3.11 recreated) |
| Legacy servers confusion | ✅ MITIGATED (archived) |
| Capability Contract drift | ✅ MITIGATED (quarterly review) |
| Branch protection 403 | ⛔ ACCEPTED (GitHub free-tier limitation) |

---

**Next**: Sprint 7 candidates — re-measure coverage at HEAD (closes the §11 gap), ADR-016+ for the Sprint 5/6 comms/voice/mobile boundaries (see `docs/ACCEPTED_RISKS.md` RISK-018–RISK-023). See `CAPABILITY_TRACKER.md` for compliance details.
