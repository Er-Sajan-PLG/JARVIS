# app/brain

<!-- generated:module_readmes begin -->

| Module | Purpose | Top-level API |
|---|---|---|
| `__init__.py` | JARVIS Brain Cognitive Orchestration Package. | — |
| `analyzer.py` | Fast Heuristic Intent Classifier. | `IntentAnalyzer`, `_detect_action()`, `_detect_domain()`, `_detect_urgency()` |
| `graph.py` | LangGraph StateGraph builder for the JARVIS cognitive loop. | `build_cognitive_graph()`, `run_cognitive_loop()`, `stream_cognitive_loop()` |
| `nodes.py` | LangGraph cognitive engine for JARVIS — Sprint 3 Capability Contract. | `_require()`, `evaluator_node()`, `intent_analyzer_node()`, `response_synthesizer_node()`, `task_planner_node()`, `tool_executor_node()` |
| `planner.py` | Slow-Path Dynamic Task Planner. | `TaskPlanner`, `_destructive_path()` |
| `runner.py` | Step-by-Step ExecutionStep Runner. | `ExecutionRunner` |
| `synthesizer.py` | Final Response Synthesizer. | `ResponseSynthesizer` |

<!-- generated:module_readmes end -->
