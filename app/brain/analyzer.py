"""Fast Heuristic Intent Classifier.

Analyzes user queries to determine complexity, required capability route (fast path vs slow path),
and required tools without incurring unnecessary LLM latency for simple requests.
"""

from dataclasses import dataclass, field
from enum import Enum
import re


class IntentComplexity(str, Enum):
    """Complexity classification of user intent."""
    DIRECT_CHAT = "direct_chat"      # Fast path: direct LLM response, no tools needed
    FILE_QUERY = "file_query"        # Reading/analyzing uploaded files or workspace
    TOOL_SEARCH = "tool_search"      # Web search, OCR, or information retrieval
    MULTI_STEP = "multi_step"        # Slow path: requires dynamic ExecutionPlan with steps


@dataclass
class IntentAnalysis:
    """Result of intent analysis."""
    complexity: IntentComplexity
    requires_tools: bool = False
    suggested_tools: list[str] = field(default_factory=list)
    confidence: float = 1.0
    reasoning: str = ""


class IntentAnalyzer:
    """Fast heuristic classifier for incoming user requests."""

    def analyze(self, query: str, has_attachments: bool = False) -> IntentAnalysis:
        """Classify user intent heuristics.

        Args:
            query: Raw user message string.
            has_attachments: True if files are attached to the message.

        Returns:
            IntentAnalysis dataclass.
        """
        text = query.strip().lower()

        if has_attachments:
            return IntentAnalysis(
                complexity=IntentComplexity.FILE_QUERY,
                requires_tools=True,
                suggested_tools=["read_file", "ocr_extract"],
                reasoning="Attachments present in request",
            )

        # Multi-step complex task indicators
        multi_step_keywords = (
            "refactor", "build", "create project", "setup", "search and analyze",
            "audit", "deploy", "run tests", "git commit", "fix bug across"
        )
        if any(kw in text for kw in multi_step_keywords):
            return IntentAnalysis(
                complexity=IntentComplexity.MULTI_STEP,
                requires_tools=True,
                suggested_tools=["file_tools", "git_tools", "shell_tools"],
                reasoning="Multi-step workflow keyword detected",
            )

        # Tool search keywords
        tool_keywords = ("search for", "find file", "look up", "read ", "list files", "ocr")
        if any(kw in text for kw in tool_keywords):
            return IntentAnalysis(
                complexity=IntentComplexity.TOOL_SEARCH,
                requires_tools=True,
                suggested_tools=["search_web", "file_tools"],
                reasoning="Information retrieval or tool keyword detected",
            )

        # Default fast path
        return IntentAnalysis(
            complexity=IntentComplexity.DIRECT_CHAT,
            requires_tools=False,
            reasoning="Simple conversation query (fast path)",
        )
