# Cognitive Brain Engine Subsystem (`app/brain/`) - Version-by-Version History

## Version-by-Version Evolutionary History

### Version v0.1.0 to v0.4.0 (`e13ee67` - `e5c6fd6`)
- **Direct Model Generation**: Monolithic `main.py` directly calling `OllamaClient.chat()`. Zero intent analysis or execution planning.

### Version v0.7.0 (`7803a93`)
- **Context Assembly Step**: `ContextBuilder` introduced to prepend retrieved long-term memory facts into the model system prompt.

### Version v2.0.0 (`8519f65`)
- **Model Task Classifier**: `ModelRouter` introduced prompt task classification (`CODE`, `STEM`, `REASONING`, `DOCS`, `GENERAL`) to pick optimal models.

### Version v2.3.0 (`c84d53b`)
- **Autonomous Tool Execution**: Introduced `ToolRegistry` and `DocumentationAgent` executing file and git tools.

### Version v3.0.0 Refactored (`f4d5e01` - `ec0dc4e`) - Current HEAD
- **Cognitive Engine Modularization (`app/brain/`)**:
  - `IntentAnalyzer` (`analyzer.py`): Categorizes prompt complexity (`DIRECT_CHAT`, `FILE_QUERY`, `TOOL_SEARCH`, `MULTI_STEP`).
  - `TaskPlanner` (`planner.py`): Generates structured `ExecutionPlan` domain objects with sequential `ExecutionStep` items.
  - `ExecutionRunner` (`runner.py`): Sequential step runner evaluating `@safety_gate` policies and handling HITL approval pause states (`AWAITING_APPROVAL`).
  - `ResponseSynthesizer` (`synthesizer.py`): Formats final answer streams and step execution provenance.
- **Active Invariants at HEAD**:
  1. Direct async interface calls (`await`) used for core cognitive execution loop.
  2. Passive event telemetry published to `InMemoryAsyncBus`.
