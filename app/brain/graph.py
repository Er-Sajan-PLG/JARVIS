"""LangGraph StateGraph builder for the JARVIS cognitive loop.

Assembles the five contract nodes into a StateGraph[CognitiveState] with the
control flow defined in CAPABILITY_CONTRACT.md §1.3:

  intent_analyzer -> task_planner -> tool_executor -> response_synthesizer -> [evaluator] -> end
                         ^              |
                         +---- interrupt (HITL) ----+

The graph is the runtime manifestation of the Capability Contract. Every node
is a pure async function of CognitiveState -> CognitiveState.
"""

from __future__ import annotations

import logging
from functools import partial
from typing import Any

from app.domain.cognitive_state import CognitiveState

logger = logging.getLogger(__name__)

try:
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dep
    LANGGRAPH_AVAILABLE = False


def build_cognitive_graph(
    analyzer: Any,
    planner: Any,
    runner: Any,
    hitl_approvals: dict[str, bool] | None = None,
    tracer: Any = None,
) -> Any:
    """Build the LangGraph StateGraph for the cognitive loop.

    Args:
        analyzer: IntentAnalyzer instance.
        planner: TaskPlanner instance.
        runner: ExecutionRunner instance.
        hitl_approvals: Optional mapping of step_id -> approved for HITL resumption.
        tracer: Optional Tracer for per-node telemetry.

    Returns:
        Compiled LangGraph StateGraph, or None if langgraph is not installed.
    """
    if not LANGGRAPH_AVAILABLE:
        logger.warning("langgraph not installed - cognitive graph unavailable")
        return None

    from app.brain.nodes import (
        evaluator_node,
        intent_analyzer_node,
        response_synthesizer_node,
        task_planner_node,
        tool_executor_node,
    )

    def _wrap(label: str, fn: Any) -> Any:
        """Wrap a node fn with OTel-style tracer span if a tracer is supplied."""
        if tracer is None:
            return fn

        async def traced(state: CognitiveState, *args: Any, **kwargs: Any) -> CognitiveState:
            async with tracer.trace(component=label, category="cognitive_node"):
                return await fn(state, *args, **kwargs)

        return traced

    graph = StateGraph(CognitiveState)

    # Add nodes - use functools.partial to inject dependencies while
    # preserving the async signature that langgraph's runner detects.
    graph.add_node(
        "intent_analyzer",
        _wrap("intent_analyzer", partial(intent_analyzer_node, analyzer=analyzer)),
    )
    graph.add_node(
        "task_planner",
        _wrap("task_planner", partial(task_planner_node, planner=planner)),
    )
    graph.add_node(
        "tool_executor",
        _wrap(
            "tool_executor",
            partial(tool_executor_node, runner=runner, hitl_approvals=hitl_approvals),
        ),
    )
    graph.add_node("response_synthesizer", _wrap("response_synthesizer", response_synthesizer_node))
    graph.add_node("evaluator", _wrap("evaluator", evaluator_node))

    # Wire the control flow per contract S1.3.
    graph.add_edge(START, "intent_analyzer")
    graph.add_edge("intent_analyzer", "task_planner")
    graph.add_edge("task_planner", "tool_executor")

    # tool_executor routes to interrupt (HITL) or synthesize.
    # On interrupt, the graph ENDS — the caller must re-run with HITL approvals.
    # This mirrors LangGraph's interrupt()/Command(resume=...) pattern: the graph
    # pauses at the DESTRUCTIVE step and only resumes when the human decision is
    # supplied as input to a subsequent invocation.
    graph.add_conditional_edges(
        "tool_executor",
        lambda s: s.get("next_node", "synthesize"),
        {
            "interrupt": END,  # pause — resume via re-invocation with hitl_approvals
            "synthesize": "response_synthesizer",
        },
    )

    graph.add_edge("response_synthesizer", "evaluator")
    graph.add_edge("evaluator", END)

    return graph.compile()


async def run_cognitive_loop(
    user_input: str,
    analyzer: Any,
    planner: Any,
    runner: Any,
    session_id: str = "default",
    hitl_approvals: dict[str, bool] | None = None,
    tracer: Any = None,
    stream: bool = False,
) -> Any:
    """Run the full cognitive loop for a single user turn.

    Args:
        user_input: Raw user message.
        analyzer: IntentAnalyzer instance.
        planner: TaskPlanner instance.
        runner: ExecutionRunner instance.
        session_id: Session identifier.
        hitl_approvals: Optional HITL approvals for resumption.
        tracer: Optional Tracer for per-node telemetry (OTel semantic conventions).
        stream: If True, return an async generator of LangGraph stream events
            (stream_mode="values") instead of the final state.

    Returns:
        Final CognitiveState after the loop completes, or an async generator
        when ``stream=True``.
    """
    graph = build_cognitive_graph(analyzer, planner, runner, hitl_approvals, tracer=tracer)
    if graph is None:
        if stream:

            async def _empty():
                yield {
                    "user_input": user_input,
                    "session_id": session_id,
                    "synthesized_response": "Cognitive graph unavailable",
                    "next_node": "end",
                }

            return _empty()
        return {
            "user_input": user_input,
            "session_id": session_id,
            "synthesized_response": "Cognitive graph unavailable (langgraph not installed)",
            "next_node": "end",
        }

    initial_state: CognitiveState = {
        "user_input": user_input,
        "session_id": session_id,
        "turn_id": 0,
        "intent": None,
        "plan": None,
        "execution_results": [],
        "synthesized_response": None,
        "safety_flags": [],
        "provenance": [],
        "next_node": "intent",
        "metadata": {},
    }

    if stream:

        async def _stream():
            async for event in graph.astream(initial_state, stream_mode="values"):
                yield event

        return _stream()

    return await graph.ainvoke(initial_state)


def stream_cognitive_loop(
    user_input: str,
    analyzer: Any,
    planner: Any,
    runner: Any,
    session_id: str = "default",
    hitl_approvals: dict[str, bool] | None = None,
    tracer: Any = None,
) -> Any:
    """Return an async generator that streams cognitive loop state updates.

    Unlike ``run_cognitive_loop``, this is **not** a coroutine — call it
    directly and iterate the result with ``async for``.
    """
    graph = build_cognitive_graph(analyzer, planner, runner, hitl_approvals, tracer=tracer)
    if graph is None:

        async def _empty():
            yield {
                "user_input": user_input,
                "session_id": session_id,
                "synthesized_response": "Cognitive graph unavailable",
                "next_node": "end",
            }

        return _empty()

    initial_state: CognitiveState = {
        "user_input": user_input,
        "session_id": session_id,
        "turn_id": 0,
        "intent": None,
        "plan": None,
        "execution_results": [],
        "synthesized_response": None,
        "safety_flags": [],
        "provenance": [],
        "next_node": "intent",
        "metadata": {},
    }
    return graph.astream(initial_state, stream_mode="values")
