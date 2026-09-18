# JARVIS Release Changelog

**Status**: ACTIVE
**Type**: changelog
**Last Updated**: 2026-09-18

All notable changes to the JARVIS project from the initial commit (`1999e53`) to the
current release are recorded here. Entries are newest-first. Versions below `v3.0.0`
are retained history and are **not** rewritten; see also
[`archive/`](archive/) for the frozen v3.0.0 release-cycle documents.

## [v3.24.0] — 2026-09-18
### Added (docs lockdown)
- Documentation coverage gate (`scripts/check_doc_coverage.py`): module,
  route and env censuses computed from the live tree (`0902b27`).
- Push refusal (`githooks/pre-push`) and CI enforcement
  (`gate_doc_coverage`); doc-coverage tests (`tests/unit/test_doc_coverage.py`).
- Full refresh: API_CONTRACT endpoint coverage, CONFIG env table, TOOLS
  runner/comms rewrite, ARCHITECTURE/VERSIONING/ROADMAP/AGENTS/RISKS factual
  updates, 8 runbooks corrected, new COMMS.md + VOICE.md.

## [v3.23.0] — 2026-09-18
### Added (comms)
- Telegram two-way bot + notify dispatcher + push VAPID key endpoint (`f92b2c3`),
  WhatsApp Cloud API send-only channel (`74fff54`), runner comms tools, chat
  email context, brief push channel and voice endpoints (`ac6544f`), Telegram
  voice notes + p2p call sidecar scaffold (`a551882`), Telegram voice input,
  chat brief intent and spoken delivery (`fe3417f`).
### Added (voice)
- STT/TTS + wake word detection (`b0122d4`); voice REST (`/api/v1/voice`) and
  voice WebSocket (`/ws/voice`) endpoints (`ac6544f`).
### Added (email/brief)
- IMAP/SMTP email integration (`687dc20`), STARTTLS/app-password fixes
  (`833e28e`), morning brief service with Slack/email delivery (`7000de1`).
### Added (mobile/APK)
- PWA manifest/service worker/push (`07eaf87`), console shell on phone
  (`35cc133`), Capacitor wrapper + Android platform + voice UI (`06ef3fe`),
  self-healing server resolution + offline banner (`bdb8b9c`), wake lock during
  generations (`2b5dea5`).
### Added (tgcall)
- P2P call sidecar scaffold under `tgcall/` (`a551882`).
### Merged (cleanup)
- `9ed894f` ci-cd gap closure, `aa63906` audit-governance, `7d921b0`
  doc-hardening cleanup, `6f8cf2b` mobile-phone-access.

## [v3.22.1] — 2026-09-16
### Changed
- Conventional Commits enforced at commit time (`ci(commit-msg)`).

## [v3.22.0] — 2026-09-15
### Added
- **ADR-015** — *Memory facts are bi-temporal, invalidated not deleted*
  (`b7affdd`): dedup write path, invalidate-not-delete, `occurs_at`.
### Changed
- README ADR count synced 14→15 (`6fc51d5`).

## [v3.21.0] — 2026-09-14
### Added
- AGY integration for Google AI Pro models (`0fe8277`); model id/name and
  parsing fixes (`06efb5c`, `64a3e18`, `b280716`).

## [v3.20.0] — 2026-09-14
### Added
- Google AI Pro OAuth login for Gemini models (`2efe508`).

## [v3.19.0] — 2026-09-14
### Fixed
- Web app backend: working chat with OpenRouter (`f69a81e`); file
  upload + conversation rename/delete with memory wipe (`91d6400`).

## [v3.18.0] — 2026-09-14
### Added
- Web API routes + ChatGPT-like frontend (`01bfff9`); settings workspace,
  custom providers, memory API types (`f50aafd`); live provider catalogue
  (`90b76fc`).

## [v3.17.0] — 2026-09-14
### Added
- Closed all capability gaps → 100% compliance (`fe66929`).

## [v3.16.1] — 2026-09-14
### Fixed
- Ported fixes from USA + closed remaining doc gaps (`bf2406e`).

## [v3.16.0] — 2026-09-14
### Added
- USA-inspired doc governance system (`20d33b9`); Reviewed markers on all
  living documents (`fbb1f4c`).

## [v3.15.4] — 2026-09-14
### Changed
- Reviewed markers added to all living documents, 56 files (`fbb1f4c`).

## [v3.15.3] — 2026-09-14
### Changed
- ROADMAP + CAPABILITY_TRACKER marked all sprints complete (`43c3581`).

## [v3.15.2] — 2026-09-14
### Added
- Memory pipeline and MCP server tests.

## [v3.15.1] — 2026-09-14
### Fixed
- Pre-commit uses cached doc facts for fast commits.

## [v3.15.0] — 2026-09-14
### Added
- Working web app with chat UI + WebSocket streaming.

## [v3.14.1] — 2026-09-14
### Changed
- Sprint 4 items marked complete in CAPABILITY_TRACKER.

## [v3.14.0] — 2026-09-14
### Added
- Sprint 4: MCP server, Cloudflare deploy, workspace awareness.

## [v3.13.1] — 2026-09-14
### Fixed
- Pre-commit hooks scoped to active source dirs only.

## [v3.13.0] — 2026-09-14
### Added
- Streaming + OTel instrumentation on the cognitive loop.

## [v3.12.0] — 2026-09-14
### Added
- Regression eval suite for CI.

## [v3.11.0] — 2026-09-14
### Added
- Session MemorySaver, fork/archive lifecycle, token-aware context trimming.

## [v3.10.0] — 2026-09-14
### Added
- Contract-compliant MemoryItem schema, LLM extractor, dedup, configurable
  hybrid fusion.

## [v3.9.0] — 2026-09-14
### Fixed
- Doc-facts: `test_count` derived once, deterministically, via `--collect-only`.

## [v3.8.0] — 2026-09-13
### Added
- Authoritative fact-computation architecture for doc facts.

## [v3.7.0] — 2026-09-13
### Added
- LangGraph cognitive engine wiring (Sprint 3 increment 01).

## [v3.6.1] — 2026-09-13
### Fixed
- Closed the silent-skip hole in the doc-facts checker.

## [v3.6.0] — 2026-09-13
### Added
- External link checking, an ADR, and the offline invariant.

## [v3.5.0] — 2026-09-13
### Added
- Doc type contract, enforced — write docs so they cannot drift.

## [v3.4.1] — 2026-09-13
### Changed
- Documented the fact system; prose quotes the anti-pattern.

## [v3.4.0] — 2026-09-13
### Added
- Doc facts sync automatically; staleness clock added.

## [v3.3.4] — 2026-09-13
### Changed
- Documented why `iter_docs()` has a narrow scope.

## [v3.3.3] — 2026-09-13
### Changed
- Recorded the measured reachability of the chromadb CVEs (RISK-001).

## [v3.3.2] — 2026-09-13
### Changed
- Enforced the versioning rule; fixed the docs that broke it.

## [v3.3.1] — 2026-09-13
### Changed
- Recorded the token reality; added doc versioning rules.

## [v3.3.0] — 2026-09-13
### Added
- Documentation hygiene enforced in the gate (`6859f04`); header migration
  made idempotent across root files (`7695f19`).
### Merged (cleanup)
- Dependabot #44, #46, #50–#53 merged (nvidia/cuda + mpmath bumps), #60 (dev).

## [v3.2.2] — 2026-09-13
### Fixed
- `pre-push` published a GitHub Release **before** pushing its tag, which `gh`
  refuses (`tag vX exists locally but has not been pushed`). The hook now pushes
  the tag first, then publishes. Pushing a tag re-enters the hook with
  `local_ref=refs/tags/…`, which the branch guard skips — no recursion.
  (`7991764`)

### Changed
- `docs/CI-TOKEN-PERMISSIONS.md` and **RISK-012** rewritten from live probes:
  branch protection is a **plan** limit, not a token-scope limit. Re-probed with
  a token that holds `administration:write` and admin permission — still the
  "Upgrade to GitHub Pro" message, and repository rulesets are gated the same
  way. (`b0f545e`)

## [v3.2.1] — 2026-09-13
### Fixed
- Release publishing was wired into `pre-push` but produced nothing on first
  use — the ordering bug above. Recorded here because the tag exists.

## [v3.2.0] — 2026-09-13
### Added
- `scripts/publish_release.py` (218 lines) + `tests/unit/test_publish_release.py`
  (9 tests). Turns a git **tag** into a GitHub **Release** — notes, compare link
  and the "Latest" marker.
- `pre-push` now publishes the release for a newly cut tag.

### Fixed
- **TD-009 closed.** GitHub showed 21 tags and **0 releases**, so release notes
  and compare links had never existed. Backfilled 20 missing releases; verified
  independently via the GitHub API — 21 tags → 21 releases. (`d10141b`)

## [v3.1.2] — 2026-09-13
### Added
- `tests/integration/test_ci_bridge_gate_loop.py` — 12 tests pinning the
  CI-bridge → `ci_gate` → status-publish loop, including the blocking-vs-
  reported-only rule and publish-failure detection. Mutation-checked: reverting
  the reported-only rule fails 2 of them. (`59eaeb6`)

### Changed
- **RISK-004 resolved.** The "~36% coverage" figure was stale; measured with the
  gate's own command, coverage is **98%** (`TOTAL 6215 141 98%`) across 1028
  passing tests. `gate_coverage` now reports `pass` against the 80% floor.
- `docs/ROADMAP.md`, `docs/ACCEPTED_RISKS.md` and
  `docs/SPRINT_1_2_COMPLETION.md` corrected to the measured values.

## [v3.1.1] — 2026-09-12
### Fixed
- Version drift: nothing ever *created* a tag, so the derived version silently
  sat at `v3.0.1+dev.148`. `scripts/version_bump.py` now computes the SemVer bump
  from conventional commits since the last release tag, and `pre-push` applies it
  (`--apply --tag-only`). It refuses to bump when there is nothing bump-worthy,
  rather than minting an empty patch tag. (`cab37e3`)

### Changed
- The mypy ratchet was lowered 494 → 485, locking the Phase-0 gain
  (`.governance/mypy_baseline.txt`). The ceiling may only move down.

## [v3.1.0] — 2026-09-12
### Added
- **ADR-013** — *JARVIS orchestrates its own work; n8n is a workflow executor it
  drives.* Settled the drift where governance named seven n8n workflows as the
  automation authority while three existed and the real CI decision lived in
  `scripts/ci_gate.py`.
- Phase-0 security fixes: WebSocket/SSE surfaces authenticated (`21bf808`), the
  file-tool allowlist enforced (`2d8d7ea`), the `ApprovalRegistry` persisted
  across a restart (`d52789f`), and the gitleaks allowlist narrowed to two fake
  fixture literals (`0f41a88`).

### Changed
- CI publishing token resolution fixed to read `.ci-bridge.env` first, so the
  service uses `JARVIS_CI_TOKEN` instead of an unrelated token from
  `~/.hermes/.env`. Verified by read-back: `state=success, total_count=8`.
  (RISK-015, `1a20495`)
- Test coverage raised 45% → 92% (`fa6c544`), then to 98%.

## [v3.0.1] — 2026-07-28
### Fixed
- The API hardcoded `version="3.0.0"`, so `/health` reported `3.0.0` while the app
  knew a longer version. It now imports the git-derived `VERSION`.

---

## [v3.0.0 Refactored]
- **Timeline Metadata**: *Feature Author Date: 2026-07-28 (`ec0dc4e`)  |  Tag Release Date: 2026-07-28*
- **Feature Author Date**: 2026-07-28 (`c5a97b4` - `ec0dc4e`)
- **Tag Release Date**: 2026-07-28

### Added
- **Domain Layer (`app/domain/`)**: Pure Python 3.11+ dataclasses (`ContentSource`, `MemoryRecord`, `ExecutionPlan`, `SessionState`, `SafetyTier`).
- **Composition Root (`app/bootstrap.py`)**: `ApplicationContainer` dependency injection container wiring system singletons.
- **Cognitive Brain Engine (`app/brain/`)**: `IntentAnalyzer`, `TaskPlanner`, `ExecutionRunner`, `ResponseSynthesizer`.
- **Tiered Tool Safety Policy (`app/guardrails/`)**: `ToolSafetyPolicy` and `@safety_gate` decorators enforcing `SAFE`, `SENSITIVE`, and `DESTRUCTIVE` approval gates.
- **Resource Manager & Circuit Breaker (`app/resources/`)**: `ResourceManager`, `TokenBudgetManager`, `RateLimitTracker`, `ProviderHealthMonitor`.
- **I/O Protocol Adapters (`app/adapters/`)**: REST HTTP routes, WebSocket / SSE streaming adapters, Bearer token authentication (`JARVIS_API_KEY`).
- **Third-Party Integrations (`app/integrations/`)**: OCR service backends and `ChromaVectorStore` wrapper isolating ChromaDB vector search.
- **Telemetry Observability (`app/telemetry/`)**: `EventLogger`, `Tracer`, `MetricsCollector`.

### Changed
- Refactored `ModelRouter` in `app/models/router.py` to support dynamic provider registration and automatic 429/503 circuit breaker failover.
- Refactored `MemoryService` in `app/memory/service.py` to act as a domain-pure memory façade.
- Reorganized test suite into `tests/unit/` and `tests/performance/`.

### Fixed
- Fixed memory file corruption handling in `MemoryStore` to automatically quarantine bad JSON files to `.corrupt-*.bak`.
- Fixed token budgeting in `ContextBuilder` to prevent context window overflow.

---

## [v3.0.0]
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 (`81e45f0`)  |  Tag Release Date: 2026-07-26*
- **Feature Author Dates**: 2026-07-19 (RAG Subsystem `e35d468`-`ba2026f`) | 2026-07-26 (Catalog Expansion `81e45f0`)
- **Tag Release Date**: 2026-07-26 (`81e45f0`, `2c855c7`, `d23f5a0`)

### Added
- **Multi-Provider Live Catalog**: Dynamic discovery of cloud and local providers (Google AI Studio, Groq, Cerebras, SambaNova, NVIDIA NIM, OpenRouter, Ollama, llama.cpp).
- **RAG & Knowledge Subsystem**: PDF extraction, OCR service integration (PaddleOCR, UnlimitedOCR), chunking, vector embedding, and paper store retrieval API (`Steps 1-9`).
- **Web UI Enhancements**: Research Papers web UI tab, active provider switcher, live status indicator.

### Changed
- Security hardening across API endpoints and input parameter sanitization.

---

## [v2.5.0]
- **Timeline Metadata**: *Feature Author Date: 2026-07-18 (`f9fa068`)  |  Tag Release Date: 2026-07-18*
- **Feature Author Date**: 2026-07-18 (`f9fa068`)
- **Tag Release Date**: 2026-07-18

### Added
- **FastAPI Web API Server**: Interactive Web UI backend with REST endpoints for chat, sessions, and memory inspection.
- **Frontend Single-Page App**: Modern dark-mode web application in `frontend/`.

---

## [v2.4.2]
- **Timeline Metadata**: *Feature Author Date: 2026-07-14 (`6034224`)  |  Tag Release Date: 2026-07-14*
- **Feature Author Date**: 2026-07-14 (`6034224`)
- **Tag Release Date**: 2026-07-14

### Added
- Ollama `Modelfile` configuration for custom system instructions and default parameters.
- Configuration updates for local model runtime paths.

---

## [v2.4.1]
- **Timeline Metadata**: *Feature Author Date: 2026-07-13 (`1cab1b1`)  |  Tag Release Date: 2026-07-14*
- **Feature Author Date**: 2026-07-13 (`1cab1b1`)
- **Tag Release Date**: 2026-07-14

### Added
- Mermaid.js architecture diagrams in `docs/architecture/`.

---

## [v2.4.0]
- **Timeline Metadata**: *Feature Author Date: 2026-07-11 (`6ea9796`)  |  Tag Release Date: 2026-07-14*
- **Feature Author Date**: 2026-07-11 (`6ea9796`)
- **Tag Release Date**: 2026-07-14

### Added
- Expanded model backends (OpenAI, Anthropic, Cohere, Mistral, Together AI, Zhipu AI, HuggingFace Inference API).
- Centralized YAML configuration system in `config.yaml`.

---

## [v2.3.0]
- **Timeline Metadata**: *Feature Author Date: 2026-07-06 (`c84d53b`)  |  Tag Release Date: 2026-07-14*
- **Feature Author Date**: 2026-07-06 (`c84d53b`)
- **Tag Release Date**: 2026-07-14

### Added
- `DocumentationAgent`: Autonomous agent loop for analyzing git history and generating CHANGELOG/DEVLOG documentation.
- Tool Infrastructure: `ToolDefinition`, `ToolRegistry`, `ToolExecutor` (`read_file`, `write_file`, `append_file`, `git_log`, `git_diff_stat`, `git_diff_full`).

---

## [v2.2.0] - 2026-07-05 (`b2c2211`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`b2c2211`)  |  Tag Release Date: 2026-07-05*

### Added
- **Semantic Vector Memory**: ChromaDB integration (`VectorRetriever`) using `OllamaEmbeddingFunction` with `nomic-embed-text`.
- **Hybrid Retrieval**: `HybridRetriever` combining vector similarity and BM25 keyword search scores.

---

## [v2.1.0] - 2026-07-05 (`df45be2`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`df45be2`)  |  Tag Release Date: 2026-07-05*

### Added
- Multi-backend architecture (`LlamaCppClient`, `OllamaClient`).
- Token-by-token response streaming over stdout/HTTP.
- External YAML configuration loader (`get_settings()`).

---

## [v2.0.0] - 2026-07-03 (`8519f65`, `5fccb37`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-03 (`8519f65`)  |  Tag Release Date: 2026-07-03*

### Added
- Complete core architectural overhaul.
- Multi-model task router (`ModelRouter`) classifying prompts into `CODE`, `STEM`, `REASONING`, `DOCS`, `GENERAL`.
- Model switcher (`ModelSwitcher`) for runtime model swap.

---

## [v1.0.0] - 2026-06-29 (`6316917`, `db51ccc`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`6316917`)  |  Tag Release Date: 2026-06-29*

### Added
- Behavior-driven memory engine supporting `append`, `replace`, `ignore`, and `delete` actions.
- Multi-trigger fact extraction pipeline from user conversation turns.

---

## [v0.8.0] - 2026-06-29 (`d43f6e9`, `2922129`, `4f71baf`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`d43f6e9`)  |  Tag Release Date: 2026-06-29*

### Added
- Structured memory record schema (`Memory` dataclass with timestamps, importance scores, categories).
- Multi-fact extraction pipeline.

---

## [v0.7.0] - 2026-06-28 (`7803a93`, `9aa2fb2`, `b145614`, `7a840ee`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`7803a93`)  |  Tag Release Date: 2026-06-28*

### Added
- `ContextBuilder` for assembling system prompts, retrieved long-term memories, and conversation history.
- Separation of persistent memory facts from conversation message turns.

---

## [v0.5.0] - 2026-06-28 (`4034bf7`, `3cc9e4b`, `94e1956`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`4034bf7`)  |  Tag Release Date: 2026-06-28*

### Added
- Persistent Memory Core storing extracted user preferences to disk.
- Conversation history tracking in `OllamaClient`.

---

## [v0.4.0] - 2026-06-27 (`e5c6fd6`, `7491e9a`, `39b3d5b`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e5c6fd6`)  |  Tag Release Date: 2026-06-27*

### Added
- `SYSTEM_PROMPT` persona configuration injection.

---

## [v0.3.0] - 2026-06-27 (`8b1d0cb`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`8b1d0cb`)  |  Tag Release Date: 2026-06-27*

### Added
- Initial project architecture and technical roadmap documents in `docs/`.

---

## [v0.2.0] - 2026-06-27 (`ded44b9`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`ded44b9`)  |  Tag Release Date: 2026-06-27*

### Added
- Interactive CLI chat loop connecting user stdin/stdout to local LLM.

---

## [v0.1.0] - 2026-06-27 (`e13ee67`, `1999e53`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e13ee67`)  |  Tag Release Date: 2026-06-27*

### Added
- Initial project repository structure (`1999e53`).
- Initial Ollama API connection client (`e13ee67`).

# v0.1.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e13ee67`)  |  Tag Release Date: 2026-06-27*
## Release Summary
### Commit Window (3 commits)
#### Commit `1999e53` - Initial project structure
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 02:44:04 +0545
#### Commit `e13ee67` - Build Jarvis v0.1: Connect to Ollama
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 03:25:01 +0545
#### Commit `e13ee67` - Build Jarvis v0.1: Connect to Ollama
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 03:25:01 +0545

# v0.2.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`ded44b9`)  |  Tag Release Date: 2026-06-27*
## Release Summary
### Commit Window (2 commits)
#### Commit `ded44b9` - v0.2: working CLI chat loop with Ollama integration
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 04:59:01 +0545
#### Commit `ded44b9` - v0.2: working CLI chat loop with Ollama integration
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 04:59:01 +0545

# v0.3.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`8b1d0cb`)  |  Tag Release Date: 2026-06-27*
## Release Summary
### Commit Window (4 commits)
#### Commit `163f8a1` - Add .gitignore for Python project
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 12:58:53 +0545
#### Commit `163f8a1` - Add .gitignore for Python project
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 12:58:53 +0545
#### Commit `8b1d0cb` - Added Architecture and Roadmap in docs for what to do seamless development
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 13:05:30 +0545
#### Commit `8b1d0cb` - Added Architecture and Roadmap in docs for what to do seamless development
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 13:05:30 +0545

# v0.4.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 (`e5c6fd6`)  |  Tag Release Date: 2026-06-27*
## Release Summary
### Commit Window (6 commits)
#### Commit `39b3d5b` - Making prompt
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 13:51:06 +0545
#### Commit `39b3d5b` - Making prompt
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 13:51:06 +0545
#### Commit `7491e9a` - prompt failure, prompts to prompt
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 14:03:01 +0545
#### Commit `7491e9a` - prompt failure, prompts to prompt
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 14:03:01 +0545
#### Commit `e5c6fd6` - added SYSTEM_PROMPT in messege
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 14:10:19 +0545
#### Commit `e5c6fd6` - added SYSTEM_PROMPT in messege
- **Author**: Er Sajan PLG | **Date**: 2026-06-27 14:10:19 +0545

# v0.5.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`4034bf7`)  |  Tag Release Date: 2026-06-28*
## Release Summary
### Commit Window (6 commits)
#### Commit `94e1956` - Implement conversation history in OllamaClient
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 02:04:26 +0545
#### Commit `94e1956` - Implement conversation history in OllamaClient
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 02:04:26 +0545
#### Commit `3cc9e4b` - change model from deepseek r1:32b to qwen3:8b for faster development
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 02:11:32 +0545
#### Commit `3cc9e4b` - change model from deepseek r1:32b to qwen3:8b for faster development
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 02:11:32 +0545
#### Commit `4034bf7` - Persistent Memory Core
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 04:52:42 +0545
#### Commit `4034bf7` - Persistent Memory Core
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 04:52:42 +0545

# v0.7.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 (`7803a93`)  |  Tag Release Date: 2026-06-28*
## Release Summary
### Commit Window (8 commits)
#### Commit `7a840ee` - Save Fact based on preferences
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 05:16:44 +0545
#### Commit `7a840ee` - Save Fact based on preferences
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 05:16:44 +0545
#### Commit `b145614` - Fact Extraction
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 05:22:19 +0545
#### Commit `b145614` - Fact Extraction
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 05:22:19 +0545
#### Commit `9aa2fb2` -  JARVIS MEMORY SEPERATION FROM CONVERSATION ANDFACTS
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 16:23:10 +0545
#### Commit `9aa2fb2` -  JARVIS MEMORY SEPERATION FROM CONVERSATION ANDFACTS
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 16:23:10 +0545
#### Commit `7803a93` - Context Builder & Long-Term Memory Integration
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 22:50:49 +0545
#### Commit `7803a93` - Context Builder & Long-Term Memory Integration
- **Author**: Er Sajan PLG | **Date**: 2026-06-28 22:50:49 +0545

# v0.8.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`d43f6e9`)  |  Tag Release Date: 2026-06-29*
## Release Summary
### Commit Window (2 commits)
#### Commit `d43f6e9` - [200~feat(v0.8): implement structured memory pipeline~
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 03:50:36 +0545
#### Commit `d43f6e9` - [200~feat(v0.8): implement structured memory pipeline~
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 03:50:36 +0545

# v1.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-06-29 (`6316917`)  |  Tag Release Date: 2026-06-29*
## Release Summary
### Commit Window (6 commits)
#### Commit `2922129` - feat(memory): implement multi-fact extraction pipeline
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 07:02:35 +0545
#### Commit `2922129` - feat(memory): implement multi-fact extraction pipeline
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 07:02:35 +0545
#### Commit `4f71baf` - feat(memory): implement behavior-driven memory engine and multi-fact extraction
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 08:56:24 +0545
#### Commit `4f71baf` - feat(memory): implement behavior-driven memory engine and multi-fact extraction
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 08:56:24 +0545
#### Commit `6316917` - feat(memory): implement multi-trigger extraction and behavior-based memory actions
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 12:13:20 +0545
#### Commit `6316917` - feat(memory): implement multi-trigger extraction and behavior-based memory actions
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 12:13:20 +0545

# v2.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-03 (`8519f65`)  |  Tag Release Date: 2026-07-03*
## Release Summary
### Commit Window (6 commits)
#### Commit `db51ccc` - feat(memory): implement multi-trigger extraction and behavior-based memory actions,left over
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 12:14:52 +0545
#### Commit `db51ccc` - feat(memory): implement multi-trigger extraction and behavior-based memory actions,left over
- **Author**: Er Sajan PLG | **Date**: 2026-06-29 12:14:52 +0545
#### Commit `63addf6` - before big change in memory management
- **Author**: Er Sajan PLG | **Date**: 2026-07-02 09:31:29 +0545
#### Commit `63addf6` - before big change in memory management
- **Author**: Er Sajan PLG | **Date**: 2026-07-02 09:31:29 +0545
#### Commit `8519f65` - feat(core)!: JARVIS v2.0.0 - Complete architectural overhaul
- **Author**: Er Sajan PLG | **Date**: 2026-07-03 23:31:02 +0545
#### Commit `8519f65` - feat(core)!: JARVIS v2.0.0 - Complete architectural overhaul
- **Author**: Er Sajan PLG | **Date**: 2026-07-03 23:31:02 +0545

# v2.1.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`df45be2`)  |  Tag Release Date: 2026-07-05*
## Release Summary
### Commit Window (4 commits)
#### Commit `5fccb37` - Bug fixes and added archiecture, dev log and changelog for v2.0.0
- **Author**: Er Sajan PLG | **Date**: 2026-07-04 18:40:14 +0545
#### Commit `5fccb37` - Bug fixes and added archiecture, dev log and changelog for v2.0.0
- **Author**: Er Sajan PLG | **Date**: 2026-07-04 18:40:14 +0545
#### Commit `df45be2` - Multi-Backend + Streaming + External Config
- **Author**: Er Sajan PLG | **Date**: 2026-07-05 07:23:59 +0545
#### Commit `df45be2` - Multi-Backend + Streaming + External Config
- **Author**: Er Sajan PLG | **Date**: 2026-07-05 07:23:59 +0545

# v2.2.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-05 (`b2c2211`)  |  Tag Release Date: 2026-07-05*
## Release Summary
### Commit Window (2 commits)
#### Commit `b2c2211` - Semantic Memory with chromaDB installed vector_retriver, hybrid_retriever with keyword retriever, conversation_store, past_exchange and ollama isnallation for ebmedding, Agent imtegration for git automation with auto make devlog and change reverted
- **Author**: Er Sajan PLG | **Date**: 2026-07-05 22:01:06 +0545
#### Commit `b2c2211` - Semantic Memory with chromaDB installed vector_retriver, hybrid_retriever with keyword retriever, conversation_store, past_exchange and ollama isnallation for ebmedding, Agent imtegration for git automation with auto make devlog and change reverted
- **Author**: Er Sajan PLG | **Date**: 2026-07-05 22:01:06 +0545

# v2.3.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-06 (`c84d53b`)  |  Tag Release Date: 2026-07-14*
## Release Summary
### Commit Window (2 commits)
#### Commit `c84d53b` - feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:47:08 +0545
#### Commit `c84d53b` - feat(agent): add DocumentationAgent, tool infrastructure, and execution framework
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:47:08 +0545

# v2.4.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-11 (`6ea9796`)  |  Tag Release Date: 2026-07-14*
## Release Summary
### Commit Window (2 commits)
#### Commit `6ea9796` - feat(platform): expand model backends and configuration system
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:47:54 +0545
#### Commit `6ea9796` - feat(platform): expand model backends and configuration system
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:47:54 +0545

# v2.4.1
- **Timeline Metadata**: *Feature Author Date: 2026-07-13 (`1cab1b1`)  |  Tag Release Date: 2026-07-14*
## Release Summary
### Commit Window (2 commits)
#### Commit `1cab1b1` - mermaid added in docs/architecture and mermaid dependencies
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:48:42 +0545
#### Commit `1cab1b1` - mermaid added in docs/architecture and mermaid dependencies
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:48:42 +0545

# v2.4.2
- **Timeline Metadata**: *Feature Author Date: 2026-07-14 (`6034224`)  |  Tag Release Date: 2026-07-14*
## Release Summary
### Commit Window (2 commits)
#### Commit `6034224` - chore: update configuration and add Ollama Modelfile
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:48:42 +0545
#### Commit `6034224` - chore: update configuration and add Ollama Modelfile
- **Author**: Er Sajan PLG | **Date**: 2026-07-14 12:48:42 +0545

# v2.5.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-18 (`f9fa068`)  |  Tag Release Date: 2026-07-18*
## Release Summary
### Commit Window (2 commits)
#### Commit `f9fa068` - feat: add web UI, FastAPI server, and fix batch of issues
- **Author**: Er Sajan PLG | **Date**: 2026-07-18 18:10:01 +0545
#### Commit `f9fa068` - feat: add web UI, FastAPI server, and fix batch of issues
- **Author**: Er Sajan PLG | **Date**: 2026-07-18 18:10:01 +0545

# v3.0.0
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 (`81e45f0`)  |  Tag Release Date: 2026-07-26*
## Release Summary
### Commit Window (18 commits)
#### Commit `e5875fa` - chore: remove stray debug artifacts (home/ duplicate, tmp/ scratch)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 10:16:49 +0545
#### Commit `e5875fa` - chore: remove stray debug artifacts (home/ duplicate, tmp/ scratch)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 10:16:49 +0545
#### Commit `e35d468` - feat(knowledge): scaffold RAG subsystem — PDF extraction, OCR, chunking
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 13:53:07 +0545
#### Commit `e35d468` - feat(knowledge): scaffold RAG subsystem — PDF extraction, OCR, chunking
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 13:53:07 +0545
#### Commit `4b93857` - feat(knowledge): add PaperStore ChromaDB layer (Step 4)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 13:59:54 +0545
#### Commit `4b93857` - feat(knowledge): add PaperStore ChromaDB layer (Step 4)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 13:59:54 +0545
#### Commit `7be0863` - feat(knowledge): add RAG answer() with grounded citations (Step 5)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 14:19:27 +0545
#### Commit `7be0863` - feat(knowledge): add RAG answer() with grounded citations (Step 5)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 14:19:27 +0545
#### Commit `5e7937b` - feat(knowledge): save findings to memory + forward metadata in MemoryManager (Step 6)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 14:31:40 +0545
#### Commit `5e7937b` - feat(knowledge): save findings to memory + forward metadata in MemoryManager (Step 6)
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 14:31:40 +0545
#### Commit `3c80fe7` - Step 7: RAG papers API + folder-scoped retrieval
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 15:36:23 +0545
#### Commit `3c80fe7` - Step 7: RAG papers API + folder-scoped retrieval
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 15:36:23 +0545
#### Commit `6e1b09a` - Step 8: Research Papers web UI
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 15:40:44 +0545
#### Commit `6e1b09a` - Step 8: Research Papers web UI
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 15:40:44 +0545
#### Commit `ba2026f` - Step 9: KNOWLEDGE.md + consolidated knowledge tests
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 15:49:02 +0545
#### Commit `ba2026f` - Step 9: KNOWLEDGE.md + consolidated knowledge tests
- **Author**: Er Sajan PLG | **Date**: 2026-07-19 15:49:02 +0545
#### Commit `81e45f0` - feat: v3.0.0 — Major Release: Provider Expansion, Live Catalog, Security & Polish
- **Author**: Er Sajan PLG | **Date**: 2026-07-26 01:40:15 +0545
#### Commit `81e45f0` - feat: v3.0.0 — Major Release: Provider Expansion, Live Catalog, Security & Polish
- **Author**: Er Sajan PLG | **Date**: 2026-07-26 01:40:15 +0545
