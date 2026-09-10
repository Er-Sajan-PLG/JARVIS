"""LangGraph-typed state for the JARVIS cognitive loop.

Maps to Capability Contract v1.0 (docs/CAPABILITY-CONTRACT.md §2 CognitiveState):
  intent: IntentAnalysis -> node: intent_analyzer
  plan:  ExecutionPlan -> node: task_planner
  steps: list[ToolResult] -> node: tool_executor
  output: str -> node: response_synthesizer
  eval: list[Result] -> node: evaluator (optional, Sprint 4)

Every state field is typed (TypedDict) per AGENTS.md §5.
Each node consumes/produces exactly the contract-defined types.
Source of truth: docs/CAPABILITY-CONTRACT.md + AGENTS.md.
"""

from typing import Any, TypedDict


class IntentState(TypedDict, total=False):
    """State after intent_analyzer node.

    Source: CAPABILITY-CONTRACT.md §2 (CognitiveState: intent).
    Produced by: app/brain/analyzer.py (IntentAnalyzer).
    """

    analysis: Any  # IntentAnalysis (from analyzer)
    session_id: str
    prompt: str


class PlanState(TypedDict, total=False):
    """State after task_planner node.

    Source: CAPABILITY-CONTRACT.md §2 (CognitiveState: plan).
    Produced by: app/brain/planner.py (TaskPlanner).
    """

    plan: Any  # ExecutionPlan
    analysis: Any  # IntentAnalysis (carried through)


class ExecutionState(TypedDict, total=False):
    """State after tool_executor node (with HITL approvals applied)."""

    executed: Any  # ExecutionPlan with completed/approved steps
    hitl_approvals: dict[str, bool]  # approval_id -> decision


class ResponseState(TypedDict, total=False):
    """State after response_synthesizer node — final stream output."""

    synthesized: str
    session_id: str
