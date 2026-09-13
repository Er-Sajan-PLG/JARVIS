# Cognitive Brain Engine Subsystem (`app/brain/`) - Version-by-Version History

**Status**: ACTIVE
**Last Updated**: 2026-09-13
**Source**: `app/brain/` at HEAD

## Version-by-Version Evolutionary History

### Version v0.1.0 to v0.4.0 (`e13ee67` - `e5c6fd6`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-27 | Tag Release Date: 2026-06-27*
- **Direct Model Generation**: Monolithic `main.py` directly calling `OllamaClient.chat()`. Zero intent analysis or execution planning.

### Version v0.7.0 (`7803a93`)
- **Timeline Metadata**: *Feature Author Date: 2026-06-28 | Tag Release Date: 2026-06-28*
- **Context Assembly Step**: `ContextBuilder` introduced to prepend retrieved long-term memory facts into the model system prompt.

### Version v2.0.0 (`8519f65`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-03 | Tag Release Date: 2026-07-03*
- **Model Task Classifier**: `ModelRouter` introduced prompt task classification (`CODE`, `STEM`, `REASONING`, `DOCS`, `GENERAL`) to pick optimal models.

### Version v2.3.0 (`c84d53b`)
- **Timeline Metadata**: *Feature Author Date: 2026-07-06 | Tag Release Date: 2026-07-14*
- **Autonomous Tool Execution**: Introduced `ToolRegistry` and `DocumentationAgent` executing file and git tools.

### Version v3.0.0 Refactored (`f4d5e01` - `ec0dc4e`) - Current HEAD
- **Timeline Metadata**: *Feature Author Date: 2026-07-19 / 2026-07-26 | Tag Release Date: 2026-07-26*
- **Cognitive Engine Modularization (`app/brain/`)**:
  - `IntentAnalyzer` (`analyzer.py`): Categorizes prompt complexity (`DIRECT_CHAT`, `FILE_QUERY`, `TOOL_SEARCH`, `MULTI_STEP`).
  - `TaskPlanner` (`planner.py`): Generates structured `ExecutionPlan` domain objects with sequential `ExecutionStep` items.
  - `ExecutionRunner` (`runner.py`): Sequential step runner evaluating `@safety_gate` policies and handling HITL approval pause states (`AWAITING_APPROVAL`).
  - `ResponseSynthesizer` (`synthesizer.py`): Formats final answer streams and step execution provenance.
- **Active Invariants at HEAD**:
  1. Direct async interface calls (`await`) used for core cognitive execution loop.
  2. Passive event telemetry published to `InMemoryAsyncBus`.
