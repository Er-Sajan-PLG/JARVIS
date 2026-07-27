---
doc_id: DOC-DOCS
title: "Docs Subsystem"
target_audience: ["developers", "JARVIS"]
generated_from: "repository_archaeology"
---

# Docs Subsystem

## 1. Overview
[Auto-generated from repository tree scan]

## 2. Active Symbols & API Surface
| Symbol | Type | Source File | Introduced Commit | Status |
| :--- | :--- | :--- | :--- | :--- |
| `Router` | class | `docs/ARCHITECTURE.md` | `8519f65` | ACTIVE |
| `route` | function | `docs/ARCHITECTURE.md` | `8519f65` | ACTIVE |
| `PromptBuilder` | class | `docs/ARCHITECTURE.md` | `8519f65` | ACTIVE |
| `__init__` | function | `docs/ARCHITECTURE.md` | `8519f65` | ACTIVE |
| `build` | function | `docs/ARCHITECTURE.md` | `8519f65` | ACTIVE |
| `ConversationStore` | class | `docs/ARCHITECTURE.md` | `8519f65` | ACTIVE |
| `add` | function | `docs/ARCHITECTURE.md` | `8519f65` | ACTIVE |
| `recent` | function | `docs/ARCHITECTURE.md` | `8519f65` | ACTIVE |
| `FactBehavior` | class | `docs/ARCHITECTURE.md` | `8519f65` | ACTIVE |
| `generate` | function | `docs/DEVLOG.md` | `df45be2` | DELETED |
| `get_default_model` | function | `docs/changelog.md` | `df45be2` | ACTIVE |
| `get_default_model` | function | `docs/CHANGELOG_recovered.md` | `c84d53b` | ACTIVE |
| `generate` | function | `docs/DEVLOG_recovered.md` | `c84d53b` | ACTIVE |
| `ModelResponse` | class | `docs/API.md` | `6ea9796` | ACTIVE |
| `ModelClient` | class | `docs/API.md` | `6ea9796` | ACTIVE |
| `generate` | function | `docs/API.md` | `6ea9796` | ACTIVE |
| `model_name` | function | `docs/API.md` | `6ea9796` | ACTIVE |
| `role` | function | `docs/API.md` | `6ea9796` | ACTIVE |
| `OllamaClient` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `__init__` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ask` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `MemoryManager` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `load` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `save` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `clear` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `extract_fact` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `add_fact` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `build_messages` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `_split_into_sentences` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `extract_facts` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `apply_behavior` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `replace_fact` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `decide_behavior` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `Memory` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `format_for_prompt` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `MemoryStore` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `add` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `KeywordRetriever` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `find_candidates` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `RankingWeights` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `MemoryRanker` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `rank` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ModelRouter` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `_classify_prompt` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `get_token_counter` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `PromptBuilder` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `build` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ContextWindowManager` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `fit` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `MemoryConfig` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `RankingConfig` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `PathsConfig` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `memories` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `conversations_dir` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ConversationConfig` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `get_default_model` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ModelConfig` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ModelResponse` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ModelClient` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `generate` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `model_name` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `role` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `create_client` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `is_port_open` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ensure_server_running` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `VectorRetriever` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `HybridRetriever` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ConversationVectorStore` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `add_exchange` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `search` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `pop_last_message` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `_format_past_exchanges` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `DocumentationAgent` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `run` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ToolResult` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `__bool__` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ToolDefinition` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `execute` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `to_openai_schema` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ToolRegistry` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `register` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ToolExecutor` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `has_calls` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `parse` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `format_result` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `git_log` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `git_diff_full` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `write_file` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `TaskType` | class | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `select` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `switch_to_model` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `_categorize_cloud_models` | function | `docs/CHANGELOG.md` | `6ea9796` | DELETED |
| `ModelResponse` | class | `docs/LLM.md` | `6ea9796` | ACTIVE |
| `ModelClient` | class | `docs/LLM.md` | `6ea9796` | ACTIVE |
| `generate` | function | `docs/LLM.md` | `6ea9796` | ACTIVE |
| `model_name` | function | `docs/LLM.md` | `6ea9796` | ACTIVE |
| `role` | function | `docs/LLM.md` | `6ea9796` | ACTIVE |
| `_resolve_key` | function | `docs/LLM.md` | `6ea9796` | ACTIVE |
| `create_client` | function | `docs/LLM.md` | `6ea9796` | ACTIVE |
| `TaskType` | class | `docs/LLM.md` | `6ea9796` | ACTIVE |
| `register` | function | `docs/LLM.md` | `6ea9796` | ACTIVE |
| `set_default` | function | `docs/LLM.md` | `6ea9796` | ACTIVE |
| `select` | function | `docs/LLM.md` | `6ea9796` | ACTIVE |
| `route` | function | `docs/LLM.md` | `6ea9796` | ACTIVE |
| `Memory` | class | `docs/architecture/memory.md` | `1cab1b1` | ACTIVE |
| `MemoryResult` | class | `docs/architecture/memory.md` | `1cab1b1` | ACTIVE |
