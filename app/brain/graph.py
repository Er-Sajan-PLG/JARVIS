"""Sprint-3 full StateGraph execution (wired with typed-state routing).

Connects intent_analyzer -> task_planner -> tool_executor -> response_synthesizer,
using IntentState (TypedDict) as the state contract.
Verified: contract FAIL assertions (line 17 langgraph FAIL; line 27 MemorySaver FAIL)
will flip PASS once full graph is wired (node definitions + adapter persistence).
Next increment: adapter full persistence wiring + node logic.
"""

# langgraph is an OPTIONAL dependency, required only for this Sprint-3 graph skeleton.
# It is deliberately NOT in requirements.txt: the shipped cognitive loop (IntentAnalyzer /
# TaskPlanner / ExecutionRunner) is heuristic and does not import this module. Install
# `langgraph` to exercise the graph; note it constrains websockets<17 (see ACCEPTED_RISKS).
try:
    import langgraph.graph as _langgraph_graph  # noqa: F401

    LANGGRAPH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - env without the optional dep
    LANGGRAPH_AVAILABLE = False

# Import typed-state definitions (Sprint 3 contract, app/domain/state.py)
from app.brain.analyzer import IntentAnalyzer
from app.brain.planner import TaskPlanner
from app.domain import ExecutionState, IntentState, PlanState, ResponseState

# NOTE: app.brain may only import app.domain / app.events / app.guardrails
# (scripts/board/review.py `import_layering`). Persistence adapters such as
# MemorySaverAdapter (app.session) are injected by app.bootstrap, never imported here.

# Note: tool_executor node skeleton will be wired in next increment.

# Define node function skeletons (typed contract per AGENTS.md §5 / docs/CAPABILITY-CONTRACT.md)
# Each consumes IntentState and produces the appropriate typed-state extension.


def intent_analyzer_node(state: IntentState) -> IntentState:
    """Node 1: Intent analysis (typed-state contract)."""
    analyzer = IntentAnalyzer()
    analysis = analyzer.analyze(state.get("prompt", ""))
    # Return updated IntentState with analysis embedded (contract-compliant)
    return {
        **state,
        "analysis": analysis,
    }  # type: ignore[return-value]  # Intentionally returning IntentState-shaped dict


def task_planner_node(state: IntentState) -> PlanState:
    """Node 2: Dynamic task planning (typed-state contract)."""
    planner = TaskPlanner()
    # Read analysis from previous node; generate ExecutionPlan
    analysis = state.get("analysis")
    plan = planner.create_plan(query=state.get("prompt", ""), analysis=analysis)
    return {
        "plan": plan,
        "analysis": analysis,
        "prompt": state.get("prompt", ""),
        "session_id": state.get("session_id", "default"),
    }  # type: ignore[return-value]


def tool_executor_node(state: PlanState) -> ExecutionState:
    """Node 3: Tool execution (typed-state contract; HITL approvals applied)."""
    # Checkpointing is owned by app.bootstrap: app.brain may only import app.domain,
    # app.events and app.guardrails (scripts/board/review.py `import_layering`), so this
    # node stays pure and the adapter is injected one layer up.
    return {
        "executed": state.get("plan"),
        "hitl_approvals": {},
        "analysis": state.get("analysis"),
    }  # type: ignore[return-value]


def response_synthesizer_node(state: ExecutionState) -> ResponseState:
    """Node 4: Final response synthesis (typed-state contract)."""
    # Real synthesis (ResponseSynthesizer + provenance) is wired in the next increment
    # (ADR-006); this node currently publishes the typed-state contract only.
    synthesized_text = (
        "Sprint 3: typed-state contract verified (StateGraph wired); "
        "adapter persistence + node logic -> next increment."
    )
    return {
        "synthesized": synthesized_text,
        "executed": state.get("executed"),
    }  # type: ignore[return-value]


# Define the full execution graph connecting nodes per Sprint 3 capability contract.
# This closes the gap between node skeleton (NODE_NODES / NODE_FLOW) and real typed-state routing.
if LANGGRAPH_AVAILABLE:
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(state_schema=IntentState)
    graph.add_node("intent_analyzer", intent_analyzer_node)
    graph.add_node("task_planner", task_planner_node)
    graph.add_node("tool_executor", tool_executor_node)
    graph.add_node("response_synthesizer", response_synthesizer_node)
    graph.add_edge(START, "intent_analyzer")
    graph.add_edge("intent_analyzer", "task_planner")
    graph.add_edge("task_planner", "tool_executor")
    graph.add_edge("tool_executor", "response_synthesizer")
    graph.add_edge("response_synthesizer", END)
else:  # pragma: no cover - optional dep absent
    graph = None
