"""Intent analysis domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IntentComplexity(str, Enum):
    """Complexity classification of user intent."""

    DIRECT_CHAT = "direct_chat"
    FILE_QUERY = "file_query"
    TOOL_SEARCH = "tool_search"
    MULTI_STEP = "multi_step"


@dataclass
class IntentAnalysis:
    """Result of intent analysis."""

    complexity: IntentComplexity
    requires_tools: bool = False
    suggested_tools: list[str] = field(default_factory=list)
    confidence: float = 1.0
    reasoning: str = ""
