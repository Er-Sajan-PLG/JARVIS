
## Commit `2c855c7` - Merge feature/unlimited-ocr-integration into main: v3.0.0 Provider Expansion, Live Catalog, Security & Polish + RAG/Knowledge subsystem (Steps 1-9)
**Author:** Er Sajan PLG | **Date:** 2026-07-26 10:03:25 +0545
**Files Modified:** 0	999	NEW_CHANGELOG.md
46	0	README.md
152	0	app/api/ocr/routes.py
547	104	app/api/server.py
12	0	app/attachments/store.py
39	37	app/config/settings.py
34	0	app/conversation/manager.py
51	0	app/knowledge/__init__.py
135	0	app/knowledge/chunk.py
241	0	app/knowledge/extract.py
102	0	app/knowledge/findings.py
126	0	app/knowledge/ingest.py
134	0	app/knowledge/rag.py
218	0	app/knowledge/store.py
2	10	app/main.py
3	0	app/memory/manager.py
198	12	app/models/factory.py
104	18	app/models/switcher.py
779	0	app/provider_registry.py
1	0	app/services/ocr/__init__.py
6	0	app/services/ocr/backends/__init__.py
51	0	app/services/ocr/backends/base.py
200	0	app/services/ocr/backends/paddle_ocr.py
149	0	app/services/ocr/backends/unlimited_ocr.py
42	0	app/services/ocr/config.py
105	0	app/services/ocr/model_manager.py
60	0	app/services/ocr/schemas.py
135	0	app/services/ocr/service.py
44	1	app/tools/file_tools.py
92	0	app/utils/anthropic_catalog.py
81	0	app/utils/cerebras_catalog.py
59	0	app/utils/cloudflare_ai_catalog.py
65	0	app/utils/cohere_catalog.py
64	0	app/utils/github_models_catalog.py
65	0	app/utils/groq_catalog.py
65	0	app/utils/hf_catalog.py
31	0	app/utils/image.py
65	0	app/utils/mistral_catalog.py
38	7	app/utils/model_selector.py
65	0	app/utils/nvidia_nim_catalog.py
106	0	app/utils/openai_catalog.py
19	1	app/utils/openrouter_catalog.py
49	0	app/utils/pdf.py
280	0	app/utils/provider_catalog.py
81	0	app/utils/together_catalog.py
65	0	app/utils/zhipu_catalog.py
1102	0	app/web_api_server.py
11	122	config.yaml
42	2	docs/AGENTS.md
2	6	docs/API.md
15	0	docs/ARCHITECTURE.md
12	0	docs/ARCHITECTURE_CONTINUE_AGENT.md
175	1682	docs/CHANGELOG.md
0	515	docs/CHANGELOG_recovered.md
12	0	docs/CONFIG.md
12	0	docs/DATABASE.md
263	2	docs/DEVLOG.md
0	1259	docs/DEVLOG_recovered.md
152	0	docs/KNOWLEDGE.md
13	0	docs/LLM.md
12	0	docs/MEMORY.md
0	848	docs/NEW_DEVLOG.md
3	3	docs/PROJECT_HISTORY.md
23	0	docs/README.md
14	0	docs/ROADMAP.md
15	1	docs/STARTUP_FLOW.md
12	0	docs/architecture/agents.md
17	0	docs/architecture/architecture.md
12	0	docs/architecture/data-flow.md
12	0	docs/architecture/memory.md
13	0	docs/architecture/models.md
12	0	docs/architecture/startup-flow.md
0	515	docs/changelog.md
13	0	docs/project_notes.md
1	0	external/Unlimited-OCR
30	0	external/remote_ocr_example/README.md
48	0	external/remote_ocr_example/service.py
727	38	frontend/app.js
121	26	frontend/index.html
2	1	frontend/package.json
230	0	frontend/styles.css
12	4	requirements.txt
1	0	server.pid
107	0	tests/test_findings.py
221	0	tests/test_knowledge.py
221	0	tests/test_papers_api.py
127	0	tests/test_rag.py
27	0	tests/test_remote_ocr.py
204	0	tests/test_store.py
**Patch Excerpt:**
```diff
commit 2c855c7ac213314e9013f3c491b96bac5fdf4c6a
Merge: e5875fa 81e45f0
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Sun Jul 26 10:03:25 2026 +0545

    Merge feature/unlimited-ocr-integration into main: v3.0.0 Provider Expansion, Live Catalog, Security & Polish + RAG/Knowledge subsystem (Steps 1-9)

 NEW_CHANGELOG.md                           |  999 ---------------
 README.md                                  |   46 +
 app/api/ocr/routes.py                      |  152 +++
 app/api/serv
```

## Commit `d23f5a0` - docs: v3.0.0 release notes
**Author:** Er Sajan PLG | **Date:** 2026-07-26 10:09:49 +0545
**Files Modified:** 99	0	CHANGELOG_v3.0.0.md
228	0	DEVLOG_v3.0.0.md
**Patch Excerpt:**
```diff
commit d23f5a05886ea49bff301dc60fa05b0ca74b6ee6
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Sun Jul 26 10:09:49 2026 +0545

    docs: v3.0.0 release notes
---
 CHANGELOG_v3.0.0.md |  99 +++++++++++++++++++++++
 DEVLOG_v3.0.0.md    | 228 ++++++++++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 327 insertions(+)

diff --git a/CHANGELOG_v3.0.0.md b/CHANGELOG_v3.0.0.md
new file mode 100644
index 0000000..a03b912
--- /dev/null
+++ b/CHANGELOG_v3.0.0.md
@@ -0,0 +1,99 @@
+# Ch
```

## Commit `41f93b9` - refactor: remove Attachments Library and Research Papers subsystems
**Author:** Er Sajan PLG | **Date:** 2026-07-27 19:03:54 +0545
**Files Modified:** 0	236	app/api/server.py
0	354	app/attachments/store.py
0	38	app/config/settings.py
0	51	app/knowledge/__init__.py
0	135	app/knowledge/chunk.py
0	241	app/knowledge/extract.py
0	102	app/knowledge/findings.py
0	126	app/knowledge/ingest.py
0	134	app/knowledge/rag.py
0	218	app/knowledge/store.py
1	5	app/tools/file_tools.py
0	247	app/web_api_server.py
0	152	docs/KNOWLEDGE.md
26	534	frontend/app.js
0	92	frontend/index.html
0	58	frontend/styles.css
0	107	tests/test_findings.py
0	221	tests/test_knowledge.py
0	221	tests/test_papers_api.py
0	127	tests/test_rag.py
0	27	tests/test_remote_ocr.py
0	204	tests/test_store.py
**Patch Excerpt:**
```diff
commit 41f93b9f8032c3abd91faac473aa941b2bc0dc70
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Mon Jul 27 19:03:54 2026 +0545

    refactor: remove Attachments Library and Research Papers subsystems
    
    - Remove app/attachments/ (AttachmentStore) and app/knowledge/ (PaperStore, RAG, chunking, findings)
    - Remove /api/attachments/* and /api/papers/* API endpoints from app/api/server.py and app/web_api_server.py
    - Remove KnowledgeConfig and related path settings from app/confi
```

## Commit `d86e203` - refactor(frontend): modularize web interface into ES modules and component stylesheets
**Author:** Er Sajan PLG | **Date:** 2026-07-27 21:10:43 +0545
**Files Modified:** 0	1077	frontend/app.js
37	0	frontend/css/base.css
235	0	frontend/css/components/chat.css
526	0	frontend/css/components/modals.css
144	0	frontend/css/components/sidebar.css
55	0	frontend/css/layout.css
21	0	frontend/css/variables.css
26	9	frontend/index.html
125	0	frontend/js/events.js
25	0	frontend/js/main.js
232	0	frontend/js/modules/chat.js
83	0	frontend/js/modules/conversations.js
32	0	frontend/js/modules/memories.js
399	0	frontend/js/modules/models.js
112	0	frontend/js/modules/settings.js
22	0	frontend/js/state.js
90	0	frontend/js/utils/api.js
33	0	frontend/js/utils/dom.js
13	495	frontend/styles.css
**Patch Excerpt:**
```diff
commit d86e203e7db54ef4fc6b87b97622ab3687f0cc0a
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Mon Jul 27 21:10:43 2026 +0545

    refactor(frontend): modularize web interface into ES modules and component stylesheets
    
    - Replace monolithic app.js with feature-focused ES modules under frontend/js/
      (state, utils, chat, conversations, models, settings, memories, events, main)
    - Split monolithic styles.css into layered stylesheets under frontend/css/
      (variables, base
```

## Commit `c5a97b4` - feat(pre-phase-0): implement pure domain models, prompt engine & event contracts
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:01:15 +0545
**Files Modified:** 1	0	.gitignore
49	32	README.md
8	0	app/artifacts/__init__.py
104	0	app/artifacts/manager.py
18	0	app/brain/__init__.py
81	0	app/brain/analyzer.py
99	0	app/brain/planner.py
130	0	app/brain/runner.py
29	0	app/brain/synthesizer.py
36	0	app/domain/__init__.py
59	0	app/domain/content.py
90	0	app/domain/conversation.py
42	0	app/domain/memory.py
82	0	app/domain/plan.py
30	0	app/domain/session.py
24	0	app/events/__init__.py
61	0	app/events/bus.py
70	0	app/events/models.py
15	0	app/guardrails/__init__.py
71	0	app/guardrails/decorator.py
84	0	app/guardrails/policy.py
8	0	app/prompt/__init__.py
82	0	app/prompt/loader.py
12	0	app/session/__init__.py
75	0	app/session/manager.py
118	0	app/session/persistence.py
24	0	docker-compose.yml
5	0	prompts/planner.md
5	0	prompts/synthesizer.md
7	0	prompts/system_base.md
51	0	tests/unit/test_prompts.py
**Patch Excerpt:**
```diff
commit c5a97b416dca6a8100bc82c98c962cfa475db021
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 00:01:15 2026 +0545

    feat(pre-phase-0): implement pure domain models, prompt engine & event contracts
    
    - Update README.md with Coding Standards and initial Subsystem Index
    - Implement pure domain models in app/domain/ (content, plan, conversation, memory, session)
    - Create app/domain/__init__.py re-exporting domain entities via __all__ with complete typing and do
```

## Commit `930fa7e` - feat(phase-1): build workspace manager, project watcher & session persistence
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:03:17 +0545
**Files Modified:** 14	0	app/workspace/__init__.py
106	0	app/workspace/manager.py
22	0	app/workspace/project.py
36	0	app/workspace/watcher.py
72	0	tests/unit/test_phase1.py
**Patch Excerpt:**
```diff
commit 930fa7e969a0614313f78052b291f4cbad6f174e
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 00:03:17 2026 +0545

    feat(phase-1): build workspace manager, project watcher & session persistence
    
    - Implement Project, FileWatcher, and WorkspaceManager in app/workspace/
    - Re-export public workspace APIs in app/workspace/__init__.py
    - Connect WorkspaceManager file loading to return ContentSource domain entities
    - Implement unit tests for ArtifactManager, W
```

## Commit `bb7e20b` - feat(phase-2): build BaseLLMProvider interface, resource manager & failover ModelRouter
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:05:35 +0545
**Files Modified:** 1	0	.gitignore
14	0	app/models/__init__.py
222	0	app/models/anthropic_client.py
113	0	app/models/cerebras_client.py
119	0	app/models/cloudflare_ai_client.py
137	0	app/models/cohere_client.py
176	0	app/models/exceptions.py
111	0	app/models/github_models_client.py
291	0	app/models/google_client.py
111	0	app/models/groq_client.py
112	0	app/models/hf_client.py
61	0	app/models/interface.py
111	0	app/models/mistral_client.py
111	0	app/models/nvidia_nim_client.py
106	0	app/models/omni_client.py
113	0	app/models/openai_client.py
119	93	app/models/router.py
113	0	app/models/together_client.py
111	0	app/models/zhipu_client.py
18	0	app/resources/__init__.py
56	0	app/resources/budget.py
17	0	app/resources/manager.py
66	0	app/resources/provider_health.py
52	0	app/resources/rate_limits.py
110	0	tests/unit/test_phase2.py
**Patch Excerpt:**
```diff
commit bb7e20b36fa47f71383ae1e8ab478871a3359b24
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 00:05:35 2026 +0545

    feat(phase-2): build BaseLLMProvider interface, resource manager & failover ModelRouter
    
    - Define BaseLLMProvider ABC and LLMResponse in app/models/interface.py
    - Implement TokenBudgetManager, RateLimitTracker, and ProviderHealthMonitor circuit breaker in app/resources/
    - Enhance ModelRouter in app/models/router.py with failover pool routing 
```

## Commit `8a34243` - feat(phase-3): build MemoryService facade & ContextBuilder prompt assembler
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:07:35 +0545
**Files Modified:** 8	0	app/context/__init__.py
113	0	app/context/builder.py
8	0	app/memory/__init__.py
126	0	app/memory/service.py
2	0	app/utils/tokenizer.py
86	0	tests/unit/test_phase3.py
**Patch Excerpt:**
```diff
commit 8a342439ae0c2ce24754f77c5e18cf170e85eaea
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 00:07:35 2026 +0545

    feat(phase-3): build MemoryService facade & ContextBuilder prompt assembler
    
    - Build MemoryService façade in app/memory/service.py wrapping vector & BM25 memory stores to return MemoryRecord domain models
    - Build ContextBuilder in app/context/builder.py assembling system prompt, user preferences, memory records, ContentSource items, and conversat
```

## Commit `f4d5e01` - feat(phase-4): build Cognitive Brain engine & wrap tools with tiered safety policy
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:10:02 +0545
**Files Modified:** 11	1	app/brain/runner.py
17	0	app/tools/__init__.py
11	37	app/tools/file_tools.py
74	0	tests/unit/test_phase4.py
**Patch Excerpt:**
```diff
commit f4d5e019ef58126b81cbcd664834e7b048552e17
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 00:10:02 2026 +0545

    feat(phase-4): build Cognitive Brain engine & wrap tools with tiered safety policy
    
    - Connect IntentAnalyzer, TaskPlanner, ExecutionRunner, and ResponseSynthesizer in app/brain/
    - Wrap atomic tools in app/tools/ (read_file, write_file, append_file, create_directory) with @safety_gate policy decorators
    - Support sync and async tool execution i
```

## Commit `fef3297` - feat(phase-5): implement telemetry observability, composition root & complete subsystem index
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:11:41 +0545
**Files Modified:** 20	12	README.md
128	0	app/bootstrap.py
15	0	app/telemetry/__init__.py
37	0	app/telemetry/logger.py
33	0	app/telemetry/metrics.py
41	0	app/telemetry/tracer.py
55	0	tests/unit/test_phase5.py
**Patch Excerpt:**
```diff
commit fef32975f2aeb39191bc52b5700a37212e486775
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 00:11:41 2026 +0545

    feat(phase-5): implement telemetry observability, composition root & complete subsystem index
    
    - Build EventLogger, Tracer, and MetricsCollector in app/telemetry/ for passive bus observability
    - Build ApplicationContainer and bootstrap_system() composition root in app/bootstrap.py
    - Finalize complete Subsystem & Module Index in README.md mapp
```

## Commit `ec0dc4e` - refactor: post-refactor cleanup, boundary isolation & dead-code elimination
**Author:** Er Sajan PLG | **Date:** 2026-07-28 00:28:43 +0545
**Files Modified:** 13	0	app/adapters/__init__.py
78	0	app/adapters/http/router.py
59	0	app/adapters/websocket/stream.py
3	3	app/api/ocr/routes.py
13	0	app/integrations/__init__.py
8	0	app/integrations/ocr/__init__.py
6	0	app/integrations/ocr/backends/__init__.py
0	0	app/{services => integrations}/ocr/backends/base.py
1	1	app/{services => integrations}/ocr/backends/paddle_ocr.py
1	1	app/{services => integrations}/ocr/backends/unlimited_ocr.py
0	0	app/{services => integrations}/ocr/config.py
3	3	app/{services => integrations}/ocr/model_manager.py
0	0	app/{services => integrations}/ocr/schemas.py
3	3	app/{services => integrations}/ocr/service.py
8	0	app/integrations/vector/__init__.py
82	0	app/integrations/vector/chroma.py
35	401	app/main.py
0	156	app/prompt/builder.py
0	1	app/services/ocr/__init__.py
0	6	app/services/ocr/backends/__init__.py
67	0	docs/INDEX.md
19	52	tests/{ => performance}/stress_test.py
0	0	tests/{ => unit}/test_issue6.py
36	52	tests/{ => unit}/test_issue9.py
6	15	tests/{ => unit}/test_issues.py
**Patch Excerpt:**
```diff
commit ec0dc4ed81f47fa29d12a12d2f333830f756ec1b
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 00:28:43 2026 +0545

    refactor: post-refactor cleanup, boundary isolation & dead-code elimination
    
    - Establish app/adapters/ I/O protocol boundary for REST HTTP routes, WebSocket / SSE streaming, and Bearer token security
    - Establish app/integrations/ third-party wrapper package isolating OCR backends and ChromaDB vector search
    - Reorganize test suite into tests/u
```

## Commit `ba29cc7` - docs: release v0.1.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 01:49:12 +0545
**Files Modified:** 17	0	docs/ADR/ADR-001-ollama-cli-integration.md
17	0	docs/ADR/ADR-002-json-file-persistent-memory.md
17	0	docs/ADR/ADR-003-multi-model-task-router.md
17	0	docs/ADR/ADR-004-chromadb-semantic-memory.md
17	0	docs/ADR/ADR-005-fastapi-web-server-and-ui.md
19	0	docs/ADR/ADR-006-pragmatic-hybrid-architecture.md
20	0	docs/ADR/ADR-007-domain-purity-and-dataclasses.md
21	0	docs/ADR/ADR-008-tiered-tool-safety-policy.md
21	0	docs/ADR/ADR-009-multi-provider-circuit-breaker-failover.md
20	0	docs/ADR/ADR-010-adapters-and-integrations-isolation.md
66	420	docs/API.md
90	172	docs/CHANGELOG.md
49	0	docs/HEALTH_REPORT.md
263	0	docs/HISTORY.md
55	58	docs/INDEX.md
24	90	docs/ROADMAP.md
1377	0	docs/SYMBOL_LINEAGE.md
10986	0	docs/api_graph.json
8	0	docs/debugging/diagnostic_matrix.md
1130	0	docs/history_graph.json
6	0	docs/knowledge_graph.json
7	0	docs/migrations/tombstones.md
11	0	docs/migrations/v2_to_v3_migration.md
36	0	docs/module_graph.json
18	0	docs/modules/adapters.md
887	0	docs/modules/app.md
25	0	docs/modules/brain.md
15	0	docs/modules/config.md
121	0	docs/modules/docs.md
32	0	docs/modules/domain.md
17	0	docs/modules/external.md
111	0	docs/modules/frontend.md
15	0	docs/modules/githooks.md
24	0	docs/modules/guardrails.md
15	0	docs/modules/home.md
20	0	docs/modules/integrations.md
23	0	docs/modules/memory.md
24	0	docs/modules/models.md
15	0	docs/modules/prompts.md
31	0	docs/modules/scripts.md
296	0	docs/modules/tests.md
15	0	docs/modules/tmp.md
23	0	docs/timelines/evolution_timeline.md
12	0	docs/timelines/symbol_timeline.md
**Patch Excerpt:**
```diff
commit ba29cc77df4e2c7e9aa517b9b2d1737c62177817
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 01:49:12 2026 +0545

    docs: release v0.1.0
---
 docs/ADR/ADR-001-ollama-cli-integration.md         |    17 +
 docs/ADR/ADR-002-json-file-persistent-memory.md    |    17 +
 docs/ADR/ADR-003-multi-model-task-router.md        |    17 +
 docs/ADR/ADR-004-chromadb-semantic-memory.md       |    17 +
 docs/ADR/ADR-005-fastapi-web-server-and-ui.md      |    17 +
 docs/ADR/ADR-006-pragmat
```

## Commit `847e9d2` - docs: release v0.3.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 01:51:31 +0545
**Files Modified:** 13	2	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit 847e9d29a7adf0cc98331148eee7ffeecefb8d73
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 01:51:31 2026 +0545

    docs: release v0.3.0
---
 docs/HISTORY.md | 15 +++++++++++++--
 1 file changed, 13 insertions(+), 2 deletions(-)

diff --git a/docs/HISTORY.md b/docs/HISTORY.md
index ddbd780..d7f380c 100644
--- a/docs/HISTORY.md
+++ b/docs/HISTORY.md
@@ -24,12 +24,23 @@
 ### [3] Commit `ded44b9` `[v0.2.0]` - v0.2: working CLI chat loop with Ollama integration
 **Author:** E
```

## Commit `a0e7cad` - docs: release v0.1.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:19 +0545
**Files Modified:** 6	1	docs/API.md
6	0	docs/ARCHITECTURE.md
10	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
16	0	docs/DEVLOG.md
20	1	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit a0e7cad7c08a87791dd267a6a5035fc1b8a51bf9
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:19 2026 +0545

    docs: release v0.1.0
---
 docs/API.md          |  7 ++++++-
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    | 10 ++++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 16 ++++++++++++++++
 docs/HISTORY.md      | 21 ++++++++++++++++++++-
 6 files changed, 64 insertions(+), 2 deletions(-)

diff --git a/docs/API.md b/docs/API.md
index 8abe
```

## Commit `1e5f698` - docs: release v0.2.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:19 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
8	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
12	0	docs/DEVLOG.md
10	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit 1e5f69896a20406bb7b61f73efb9ad91a7e85f08
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:19 2026 +0545

    docs: release v0.2.0
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    |  8 ++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 12 ++++++++++++
 docs/HISTORY.md      | 10 ++++++++++
 6 files changed, 48 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index b478e3a..4a94267 100644
--- a/docs/API
```

## Commit `86b2eda` - docs: release v0.3.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:19 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
12	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
20	0	docs/DEVLOG.md
16	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit 86b2edaad765a80db54dd0bf16b0546908dfc401
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:19 2026 +0545

    docs: release v0.3.0
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    | 12 ++++++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 20 ++++++++++++++++++++
 docs/HISTORY.md      | 16 ++++++++++++++++
 6 files changed, 66 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index 4a94267..b30db15 100
```

## Commit `f92c68d` - docs: release v0.4.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:20 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
16	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
28	0	docs/DEVLOG.md
22	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit f92c68d0649fb9f5a31aa66240a74764dc758b62
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:20 2026 +0545

    docs: release v0.4.0
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    | 16 ++++++++++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 28 ++++++++++++++++++++++++++++
 docs/HISTORY.md      | 22 ++++++++++++++++++++++
 6 files changed, 84 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index b3
```

## Commit `62cb88d` - docs: release v0.5.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:20 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
16	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
28	0	docs/DEVLOG.md
22	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit 62cb88d0ac39632a7b0e6ad1620e43ff132a4d29
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:20 2026 +0545

    docs: release v0.5.0
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    | 16 ++++++++++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 28 ++++++++++++++++++++++++++++
 docs/HISTORY.md      | 22 ++++++++++++++++++++++
 6 files changed, 84 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index 1c
```

## Commit `a07c900` - docs: release v0.7.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:21 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
20	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
36	0	docs/DEVLOG.md
28	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit a07c9003248db4afc2a92ac99cb69e89ef27161d
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:21 2026 +0545

    docs: release v0.7.0
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    | 20 ++++++++++++++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 36 ++++++++++++++++++++++++++++++++++++
 docs/HISTORY.md      | 28 ++++++++++++++++++++++++++++
 6 files changed, 102 insertions(+)

diff --git a/docs/API.md b/d
```

## Commit `3abe471` - docs: release v0.8.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:21 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
8	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
12	0	docs/DEVLOG.md
10	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit 3abe471741789d5c3343fb95ca7c270433ec0224
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:21 2026 +0545

    docs: release v0.8.0
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    |  8 ++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 12 ++++++++++++
 docs/HISTORY.md      | 10 ++++++++++
 6 files changed, 48 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index 5883deb..4730660 100644
--- a/docs/API
```

## Commit `b6632d6` - docs: release v1.0.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:21 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
16	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
28	0	docs/DEVLOG.md
22	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit b6632d6e0a29e8ec92084de95dac1fb45c7ea72f
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:21 2026 +0545

    docs: release v1.0.0
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    | 16 ++++++++++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 28 ++++++++++++++++++++++++++++
 docs/HISTORY.md      | 22 ++++++++++++++++++++++
 6 files changed, 84 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index 47
```

## Commit `136c47c` - docs: release v2.0.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:22 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
16	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
28	0	docs/DEVLOG.md
22	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit 136c47c8e3ffa476af318ff93627e4eb27cd9680
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:22 2026 +0545

    docs: release v2.0.0
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    | 16 ++++++++++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 28 ++++++++++++++++++++++++++++
 docs/HISTORY.md      | 22 ++++++++++++++++++++++
 6 files changed, 84 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index 6c
```

## Commit `bf777f1` - docs: release v2.1.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:22 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
12	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
20	0	docs/DEVLOG.md
16	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit bf777f1dcb47ed320fccb0375bb61e29ad7c59d1
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:22 2026 +0545

    docs: release v2.1.0
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    | 12 ++++++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 20 ++++++++++++++++++++
 docs/HISTORY.md      | 16 ++++++++++++++++
 6 files changed, 66 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index de2effc..42bf651 100
```

## Commit `6ec582f` - docs: release v2.2.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:22 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
8	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
12	0	docs/DEVLOG.md
10	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit 6ec582fa0a85bce7ef88f53bfc5aaf6b4bef8df8
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:22 2026 +0545

    docs: release v2.2.0
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    |  8 ++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 12 ++++++++++++
 docs/HISTORY.md      | 10 ++++++++++
 6 files changed, 48 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index 42bf651..e3bf666 100644
--- a/docs/API
```

## Commit `0f6d478` - docs: release v2.3.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:22 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
8	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
12	0	docs/DEVLOG.md
10	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit 0f6d478f483c7dec616abc6c58db4a14e771be80
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:22 2026 +0545

    docs: release v2.3.0
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    |  8 ++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 12 ++++++++++++
 docs/HISTORY.md      | 10 ++++++++++
 6 files changed, 48 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index e3bf666..0647aa9 100644
--- a/docs/API
```

## Commit `481a668` - docs: release v2.4.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:22 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
8	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
12	0	docs/DEVLOG.md
10	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit 481a668567ed4c8972a7afadc113419113be254f
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:22 2026 +0545

    docs: release v2.4.0
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    |  8 ++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 12 ++++++++++++
 docs/HISTORY.md      | 10 ++++++++++
 6 files changed, 48 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index 0647aa9..bc15d38 100644
--- a/docs/API
```

## Commit `28dc0eb` - docs: release v2.4.1
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:23 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
8	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
12	0	docs/DEVLOG.md
10	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit 28dc0eb56d702c621a79ec69f4db46b41e43b3da
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:23 2026 +0545

    docs: release v2.4.1
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    |  8 ++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 12 ++++++++++++
 docs/HISTORY.md      | 10 ++++++++++
 6 files changed, 48 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index bc15d38..31e00c5 100644
--- a/docs/API
```

## Commit `a1951bc` - docs: release v2.4.2
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:23 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
8	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
12	0	docs/DEVLOG.md
10	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit a1951bcde6c48a5c36a2543cc478dd6872911feb
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:23 2026 +0545

    docs: release v2.4.2
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    |  8 ++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 12 ++++++++++++
 docs/HISTORY.md      | 10 ++++++++++
 6 files changed, 48 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index 31e00c5..b862115 100644
--- a/docs/API
```

## Commit `f5c2344` - docs: release v2.5.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:23 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
8	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
12	0	docs/DEVLOG.md
10	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit f5c234483205fbaf918499d6f6f89e254109677d
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:23 2026 +0545

    docs: release v2.5.0
---
 docs/API.md          |  6 ++++++
 docs/ARCHITECTURE.md |  6 ++++++
 docs/CHANGELOG.md    |  8 ++++++++
 docs/DEBUGGING.md    |  6 ++++++
 docs/DEVLOG.md       | 12 ++++++++++++
 docs/HISTORY.md      | 10 ++++++++++
 6 files changed, 48 insertions(+)

diff --git a/docs/API.md b/docs/API.md
index b862115..abcc44e 100644
--- a/docs/API
```

## Commit `8b551de` - docs: release v3.0.0
**Author:** Er Sajan PLG | **Date:** 2026-07-28 02:01:24 +0545
**Files Modified:** 6	0	docs/API.md
6	0	docs/ARCHITECTURE.md
40	0	docs/CHANGELOG.md
6	0	docs/DEBUGGING.md
76	0	docs/DEVLOG.md
58	0	docs/HISTORY.md
**Patch Excerpt:**
```diff
commit 8b551dea220ec6b803b95ff226ad3b2d1c5c5cca
Author: Er Sajan PLG <gurungsajan0228gmail.com>
Date:   Tue Jul 28 02:01:24 2026 +0545

    docs: release v3.0.0
---
 docs/API.md          |  6 +++++
 docs/ARCHITECTURE.md |  6 +++++
 docs/CHANGELOG.md    | 40 +++++++++++++++++++++++++++
 docs/DEBUGGING.md    |  6 +++++
 docs/DEVLOG.md       | 76 ++++++++++++++++++++++++++++++++++++++++++++++++++++
 docs/HISTORY.md      | 58 +++++++++++++++++++++++++++++++++++++++
 6 files changed, 192 insertions(+
```
