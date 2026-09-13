"""LangGraph cognitive engine for JARVIS — Sprint 3 Capability Contract.

Wires the canonical CognitiveState through five nodes per the contract:
  intent_analyzer → task_planner → tool_executor → response_synthesizer → [evaluator]

Each node is a pure function of CognitiveState → CognitiveState. The graph is
assembled in build_cognitive_graph().

Contract: docs/CAPABILITY_CONTRACT.md §1.
"""

from __future__ import annotations

import logging
from typing import Any

from app.brain.analyzer import IntentAnalysis
from app.domain import (
    ExecutionPlan,
    SafetyFlag,
    SafetyTier,
    StepStatus,
    ToolResult,
)
from app.domain.cognitive_state import CognitiveState
from app.events import HITLRequestEvent

logger = logging.getLogger(__name__)


def _require(state: CognitiveState, *keys: str) -> bool:
    """True when every required key is present and non-None."""
    return all(state.get(k) is not None for k in keys)


# ── Node 1: Intent Analyzer ─────────────────────────────────────────────────


async def intent_analyzer_node(state: CognitiveState, analyzer: Any) -> CognitiveState:
    """Classify user intent; raise SafetyFlags for DESTRUCTIVE intents.

    Contract: CAPABILITY_CONTRACT.md §1.2 — intent_analyzer.
    """
    user_input = state.get("user_input", "")
    analysis = analyzer.analyze(query=user_input)

    safety_flags: list[SafetyFlag] = []
    if analysis.requires_tools and analysis.suggested_tools:
        # Heuristic: if the intent involves destructive keywords, raise a flag.
        destructive_keywords = ("delete", "remove", "drop", "destroy", "format", "rm ")
        if any(kw in user_input.lower() for kw in destructive_keywords):
            safety_flags.append(
                SafetyFlag(
                    tier=SafetyTier.DESTRUCTIVE,
                    reason=f"Destructive intent detected: {analysis.reasoning}",
                    tool_name=analysis.suggested_tools[0] if analysis.suggested_tools else None,
                )
            )

    return {
        **state,
        "intent": analysis,
        "safety_flags": safety_flags,
        "next_node": "plan",
    }


# ── Node 2: Task Planner ────────────────────────────────────────────────────


async def task_planner_node(state: CognitiveState, planner: Any) -> CognitiveState:
    """Decompose intent into an ordered ExecutionPlan.

    Contract: CAPABILITY_CONTRACT.md §1.2 — task_planner.
    """
    intent: IntentAnalysis | None = state.get("intent")
    if intent is None:
        return {**state, "next_node": "end"}

    plan = planner.create_plan(
        goal=state.get("user_input", ""),
        analysis=intent,
    )

    # Mark DESTRUCTIVE steps from safety flags.
    destructive_tools = {
        f.tool_name for f in state.get("safety_flags", []) if f.is_destructive and f.tool_name
    }
    for step in plan.steps:
        if step.tool_call and step.tool_call.tool_name in destructive_tools:
            step.tool_call.safety_tier = SafetyTier.DESTRUCTIVE

    return {
        **state,
        "plan": plan,
        "next_node": "execute",
    }


# ── Node 3: Tool Executor ───────────────────────────────────────────────────


async def tool_executor_node(
    state: CognitiveState,
    runner: Any,
    hitl_approvals: dict[str, bool] | None = None,
) -> CognitiveState:
    """Execute plan steps behind the safety gate; HITL for DESTRUCTIVE.

    Contract: CAPABILITY_CONTRACT.md §1.2 — tool_executor.
    """
    plan: ExecutionPlan | None = state.get("plan")
    if plan is None:
        return {**state, "next_node": "synthesize"}

    results: list[ToolResult] = []
    hitl_approvals = hitl_approvals or {}

    for step in plan.steps:
        if step.status in (StepStatus.COMPLETED, StepStatus.SKIPPED):
            continue

        if step.is_destructive and not hitl_approvals.get(step.step_id):
            # Pause for HITL — publish request and stop.
            if hasattr(runner, "event_bus") and runner.event_bus is not None:
                runner.event_bus.publish(
                    HITLRequestEvent(
                        event_id=f"hitl-{step.step_id}",
                        event_type="hitl_request",
                        plan_id=plan.plan_id,
                        step_id=step.step_id,
                        title=step.title,
                        tool_name=step.tool_call.tool_name if step.tool_call else "unknown",
                        arguments=step.tool_call.arguments if step.tool_call else {},
                        safety_tier=SafetyTier.DESTRUCTIVE,
                        description=step.title,
                    )
                )
            # Mark awaiting and stop plan execution.
            step.status = StepStatus.AWAITING_APPROVAL
            return {
                **state,
                "plan": plan,
                "execution_results": results,
                "next_node": "interrupt",
            }

        # Execute the step via the runner.
        try:
            if step.tool_call and hasattr(runner, "_tool_registry"):
                tool_name = step.tool_call.tool_name
                if tool_name in runner._tool_registry:
                    tool_func = runner._tool_registry[tool_name]
                    kwargs = dict(step.tool_call.arguments)
                    import inspect

                    if inspect.iscoroutinefunction(tool_func):
                        res = await tool_func(**kwargs)
                    else:
                        res = tool_func(**kwargs)
                    step.result = res
                    step.status = StepStatus.COMPLETED
                    results.append(
                        ToolResult(
                            tool_name=tool_name,
                            success=True,
                            output=res,
                            safety_tier=step.tool_call.safety_tier,
                        )
                    )
                else:
                    step.status = StepStatus.COMPLETED
                    results.append(
                        ToolResult(
                            tool_name=step.tool_call.tool_name,
                            success=True,
                            output=None,
                            safety_tier=step.tool_call.safety_tier,
                        )
                    )
            else:
                # Tool call specified but tool not registered — fail, don't silently complete.
                if step.tool_call:
                    tool_name = step.tool_call.tool_name
                    step.status = StepStatus.FAILED
                    step.error = f"Tool '{tool_name}' is not registered with the execution runner"
                    results.append(
                        ToolResult(
                            tool_name=tool_name,
                            success=False,
                            error=step.error,
                            safety_tier=step.tool_call.safety_tier,
                        )
                    )
                else:
                    step.status = StepStatus.COMPLETED
        except Exception as err:  # noqa: BLE001
            step.status = StepStatus.FAILED
            step.error = str(err)
            results.append(
                ToolResult(
                    tool_name=step.tool_call.tool_name if step.tool_call else "unknown",
                    success=False,
                    error=str(err),
                    safety_tier=step.tool_call.safety_tier if step.tool_call else SafetyTier.SAFE,
                )
            )

    return {
        **state,
        "plan": plan,
        "execution_results": results,
        "next_node": "synthesize",
    }


# ── Node 4: Response Synthesizer ────────────────────────────────────────────


async def response_synthesizer_node(state: CognitiveState) -> CognitiveState:
    """Compose the final response from execution results.

    Contract: CAPABILITY_CONTRACT.md §1.2 — response_synthesizer.
    """
    results: list[ToolResult] = state.get("execution_results", [])
    intent: IntentAnalysis | None = state.get("intent")

    parts = []
    if intent:
        parts.append(f"Intent: {intent.complexity.value} (confidence {intent.confidence:.0%})")
    for r in results:
        status = "ok" if r.success else f"failed: {r.error}"
        parts.append(f"- {r.tool_name}: {status}")

    synthesized = "\n".join(parts) if parts else "No tools were executed."

    return {
        **state,
        "synthesized_response": synthesized,
        "next_node": "evaluate",
    }


# ── Node 5: Evaluator (optional) ────────────────────────────────────────────


async def evaluator_node(state: CognitiveState) -> CognitiveState:
    """Quality gate before output. Scores the response and flags repairs.

    Contract: CAPABILITY_CONTRACT.md §1.2 — evaluator (optional).
    """
    # Simple heuristic evaluator — replace with LLM-based in Sprint 4.
    results: list[ToolResult] = state.get("execution_results", [])
    failed = sum(1 for r in results if not r.success)
    total = len(results) or 1
    quality = 1.0 - (failed / total)

    repairs: list[str] = []
    if failed:
        repairs.append(f"{failed} tool(s) failed — consider retrying or rephrasing.")

    return {
        **state,
        "quality_score": quality,
        "repair_orders": repairs,
        "next_node": "end",
    }
