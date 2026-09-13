"""Canonical cognitive state for the JARVIS LangGraph loop.

Single source of truth for the Capability Contract v1.0 (docs/CAPABILITY-CONTRACT.md S1).
Both JARVIS and PROFESSOR-J implement to this shape; patterns are ported, not imported.

Every field is typed (TypedDict). Nodes consume and produce exact keys per the contract.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from app.domain.intent import IntentAnalysis
from app.domain.plan import ExecutionPlan
from app.domain.safety_flag import SafetyFlag
from app.domain.tool_result import ToolResult


class CognitiveState(TypedDict, total=False):
    """The single state object that flows through every node of the cognitive loop.

    Contract: docs/CAPABILITY-CONTRACT.md S1.1 CognitiveState.
    Node I/O: docs/CAPABILITY_CONTRACT.md S1.2 Required Nodes.
    """

    # ── Immutable per-turn ─────────────────────────────────────────────────
    session_id: str
    turn_id: int
    user_input: str

    # ── Mutable during turn ────────────────────────────────────────────────
    intent: IntentAnalysis | None  # intent_analyzer output
    plan: ExecutionPlan | None  # task_planner output
    execution_results: list[ToolResult]  # tool_executor output
    synthesized_response: str | None  # response_synthesizer output

    # ── Safety / provenance ────────────────────────────────────────────────
    safety_flags: list[SafetyFlag]  # DESTRUCTIVE intents raise these
    provenance: list[dict[str, Any]]  # PROFESSOR-J: cite LHS ids + draft status

    # ── Control ────────────────────────────────────────────────────────────
    next_node: Literal["intent", "plan", "execute", "synthesize", "evaluate", "interrupt", "end"]
    metadata: dict[str, Any]  # extensible, contract-safe

    # ── Evaluator (optional node) ──────────────────────────────────────────
    quality_score: float | None  # 0.0-1.0, evaluator output
    repair_orders: list[str]  # evaluator output: what to fix
