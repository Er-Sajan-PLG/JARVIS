"""Cognitive graph evals — verify the LangGraph cognitive loop runs end-to-end."""

from __future__ import annotations

from evals.eval import EvalResult, EvalStatus


class CognitiveGraphEval:
    """The cognitive graph runs intent→plan→execute→synthesize→evaluate."""

    name = "cognitive_graph"

    async def run(self) -> EvalResult:
        try:
            from app.brain import ExecutionRunner, IntentAnalyzer, TaskPlanner
            from app.brain.graph import run_cognitive_loop

            result = await run_cognitive_loop(
                "list files",
                IntentAnalyzer(),
                TaskPlanner(),
                ExecutionRunner(),
            )
            if result.get("next_node") != "end":
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message=f"expected next_node=end, got {result.get('next_node')}",
                )
            if not result.get("synthesized_response"):
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message="no synthesized_response",
                )
            return EvalResult(
                name=self.name,
                status=EvalStatus.PASS,
                score=1.0,
                message="cognitive loop completed",
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
