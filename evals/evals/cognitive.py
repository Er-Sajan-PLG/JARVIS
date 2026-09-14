"""Cognitive graph evals — verify the LangGraph cognitive loop runs end-to-end."""

from __future__ import annotations

from evals.eval import EvalResult, EvalStatus


class CognitiveGraphEval:
    """The cognitive graph runs intent→plan→execute→synthesize→evaluate."""

    name = "cognitive_graph"

    async def run(self) -> EvalResult:
        try:
            from app.brain import ExecutionRunner, IntentAnalyzer, TaskPlanner
            from app.brain.graph import stream_cognitive_loop

            gen = stream_cognitive_loop(
                "list files", IntentAnalyzer(), TaskPlanner(), ExecutionRunner()
            )
            events = []
            async for event in gen:
                events.append(event)

            if not events:
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message="no stream events",
                )
            if events[-1].get("next_node") != "end":
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message=f"final state not end: {events[-1].get('next_node')}",
                )
            return EvalResult(
                name=self.name,
                status=EvalStatus.PASS,
                score=1.0,
                message=f"stream yielded {len(events)} events, ended correctly",
            )
        except Exception as e:
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message=f"exception: {e}",
            )


class CognitiveGraphNodesEval:
    """All required cognitive nodes exist and are importable."""

    name = "cognitive_graph_nodes"

    async def run(self) -> EvalResult:
        try:
            from app.brain.nodes import (
                evaluator_node,
                intent_analyzer_node,
                response_synthesizer_node,
                task_planner_node,
                tool_executor_node,
            )

            nodes = [
                intent_analyzer_node,
                task_planner_node,
                tool_executor_node,
                response_synthesizer_node,
                evaluator_node,
            ]
            if not all(callable(n) for n in nodes):
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message="not all nodes are callable",
                )
            return EvalResult(
                name=self.name,
                status=EvalStatus.PASS,
                score=1.0,
                message="all 5 cognitive nodes importable and callable",
            )
        except ImportError as e:
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message=f"import error: {e}",
            )
