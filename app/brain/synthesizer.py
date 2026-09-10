"""Final Response Synthesizer.

Assembles the final streaming LLM response chunks, injecting provenance citations, tool outputs, and formatted output.
"""

from typing import AsyncGenerator

from app.domain import ExecutionPlan, Message, Role


from langgraph.graph import StateGraph, START, END  # Sprint 3: graph wiring skeleton
NODE_FLOW = ("intent_analyzer", "task_planner", "tool_executor", "response_synthesizer")


class ResponseSynthesizer:
    """Assembles final user response streams."""

    async def synthesize_stream(
        self,
        raw_stream: AsyncGenerator[str, None],
        plan: ExecutionPlan | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens to client with provenance header formatting.

        Args:
            raw_stream: Async generator of raw LLM token strings.
            plan: Optional ExecutionPlan associated with request.

        Yields:
            Token chunks ready for SSE delivery.
        """
        async for token in raw_stream:
            yield token
