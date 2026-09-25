"""Fast Heuristic Intent Classifier.

Analyzes user queries to determine complexity, required capability route (fast path vs slow path),
and required tools without incurring unnecessary LLM latency for simple requests.
"""

import logging

from app.domain import IntentAnalysis, IntentComplexity

logger = logging.getLogger(__name__)


# Sprint 3 (ADR-006): node names for the typed-state graph skeleton. These are consumed
# by app/brain/graph.py. NB: the langgraph package is NOT a runtime dependency of the
# cognitive loop — the loop uses the heuristic IntentAnalyzer below. See graph.py.
NODE_NODES = {"intent_analyzer", "task_planner", "tool_executor", "response_synthesizer"}


# Migration Step 4: additive detectors. Classification branches below are
# unchanged; these only populate the new IntentAnalysis fields (no consumers yet).
_CRITICAL_WORDS = ("urgent", "asap", "immediately", "emergency", "critical")
_HIGH_WORDS = ("quick", "fast", "hurry", "soon")
_LOW_PHRASES = ("when you have time", "whenever", "no rush")

_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "coding": (
        "code",
        "function",
        "bug",
        "python",
        "javascript",
        "api",
        "debug",
        "git",
        "commit",
        "refactor",
    ),
    "science": ("physics", "chemistry", "biology", "math", "equation", "theorem", "hypothesis"),
    "finance": ("money", "invest", "stock", "budget", "expense", "crypto", "tax"),
    "health": ("exercise", "diet", "sleep", "workout", "calories", "medical", "symptom"),
    "writing": ("write", "essay", "article", "blog", "draft", "edit"),
    "research": ("research", "investigate", "deep dive", "analyze data"),
}


def _detect_urgency(text: str) -> str:
    """Urgency heuristic. Precedence: critical > high > low > normal."""
    if any(word in text for word in _CRITICAL_WORDS):
        return "critical"
    if any(word in text for word in _HIGH_WORDS):
        return "high"
    if any(phrase in text for phrase in _LOW_PHRASES):
        return "low"
    return "normal"


def _detect_domain(text: str) -> str:
    """Domain heuristic. Most keyword hits wins (coding first on ties); else general."""
    best_domain = "general"
    best_hits = 0
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in text)
        if hits > best_hits:
            best_domain = domain
            best_hits = hits
    return best_domain


def _detect_action(text: str) -> str | None:
    """Requested-action heuristic. None means no specific action detected."""
    if any(phrase in text for phrase in ("create file", "write file", "save to", "generate file")):
        return "file_write"
    if any(phrase in text for phrase in ("read file", "open file", "show me")):
        return "file_read"
    if any(phrase in text for phrase in ("search for", "look up", "find online")):
        return "web_search"
    if any(phrase in text for phrase in ("turn on", "turn off", "lights")):
        return "hardware_control"
    return None


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
        # Migration Step 4: additive only — classification branches below unchanged.
        urgency = _detect_urgency(text)
        domain = _detect_domain(text)
        action = _detect_action(text)

        if has_attachments:
            return IntentAnalysis(
                complexity=IntentComplexity.FILE_QUERY,
                requires_tools=True,
                suggested_tools=["read_file", "ocr_extract"],
                reasoning="Attachments present in request",
                urgency=urgency,
                domain=domain,
                action=action,
            )

        # Multi-step complex task indicators
        multi_step_keywords = (
            "refactor",
            "build",
            "create project",
            "setup",
            "search and analyze",
            "audit",
            "deploy",
            "run tests",
            "git commit",
            "fix bug across",
        )
        if any(kw in text for kw in multi_step_keywords):
            return IntentAnalysis(
                complexity=IntentComplexity.MULTI_STEP,
                requires_tools=True,
                suggested_tools=["file_tools", "git_tools", "shell_tools"],
                reasoning="Multi-step workflow keyword detected",
                urgency=urgency,
                domain=domain,
                action=action,
            )

        # Tool search keywords
        tool_keywords = ("search for", "find file", "look up", "read ", "list files", "ocr")
        if any(kw in text for kw in tool_keywords):
            return IntentAnalysis(
                complexity=IntentComplexity.TOOL_SEARCH,
                requires_tools=True,
                suggested_tools=["search_web", "file_tools"],
                reasoning="Information retrieval or tool keyword detected",
                urgency=urgency,
                domain=domain,
                action=action,
            )

        # Fast path: plain conversation. NB: this must return IntentAnalysis, like every
        # other branch — the typed-state (IntentState) wrapping belongs in the graph node
        # (app/brain/graph.py intent_analyzer_node), not in the analyzer itself.
        return IntentAnalysis(
            complexity=IntentComplexity.DIRECT_CHAT,
            requires_tools=False,
            reasoning="Simple conversation query (fast path)",
            urgency=urgency,
            domain=domain,
            action=action,
        )
