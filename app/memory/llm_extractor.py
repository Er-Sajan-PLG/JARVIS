"""LLM-backed fact extraction for the memory pipeline (Sprint 3 contract §2).

The rule-based :func:`app.memory.fact_extractor.extract_facts` catches explicit
statements ("my name is X"). That cannot infer *kind* or *scope* or attach
confidence — which the capability contract requires. This module adds an LLM
extractor that classifies each extracted fact and emits ``MemoryItem``
candidates.

The ``ChatModel`` is injected (never constructed here) so the extractor is
deterministic to test: pass a stub whose ``generate`` returns fixed JSON.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Protocol

from app.domain import DraftStatus, MemoryItem, MemoryKind, MemoryScope

logger = logging.getLogger(__name__)


class ChatModel(Protocol):
    """Minimal structural interface the extractor needs from an LLM client.

    Defined locally (structural typing) rather than importing
    ``app.models.client.ModelClient``, so ``app.memory`` stays within its
    governance boundary (``app.memory -> app.integrations``). Any object with a
    compatible ``generate`` satisfies this protocol.
    """

    def generate(self, messages: list[dict[str, str]], **kwargs: Any) -> Any:
        """Return an object with a ``content`` attribute (str)."""
        ...


_EXTRACTION_PROMPT = (
    "Extract durable memories from the following conversation turn. For each, "
    "return JSON with exactly this shape, one object per line, in a JSON array: "
    '[{"content": str, "kind": "fact|episode|procedure|preference|conversation", '
    '"scope": "session|user|global", "confidence": float (0..1)}]. '
    "Do not invent facts not stated. Output only the JSON array."
)


class LLMFactExtractor:
    """Extract ``MemoryItem`` candidates from conversation text via an LLM.

    Produces richer, kind/scope/confidence-aware memories than the rule-based
    extractor, while remaining swappable because both expose a similar surface.
    Falls back to an empty result on malformed output rather than raising.
    """

    def __init__(self, model: ChatModel) -> None:
        self._model = model

    def extract(
        self,
        message: str,
        source: str = "user",
        session_id: str | None = None,
    ) -> list[MemoryItem]:
        """Extract ``MemoryItem`` candidates from a single message.

        Args:
            message: The conversation turn to mine for memories.
            source: Provenance label (user / tool / inferred / ...).
            session_id: Optional session id, attached as metadata.

        Returns:
            A list of ``MemoryItem`` candidates (possibly empty on failure).
        """
        if not message.strip():
            return []

        response = self._model.generate(
            [
                {"role": "system", "content": _EXTRACTION_PROMPT},
                {"role": "user", "content": message},
            ]
        )
        return self._parse(response.content, source=source, session_id=session_id)

    def _parse(self, raw: str, source: str, session_id: str | None) -> list[MemoryItem]:
        parsed = self._try_parse_json(raw)
        if not parsed:
            return []

        items: list[MemoryItem] = []
        for entry in parsed:
            content = str(entry.get("content", "")).strip()
            if not content:
                continue
            items.append(
                MemoryItem(
                    id=str(uuid.uuid4()),
                    content=content,
                    kind=self._kind(entry.get("kind")),
                    scope=self._scope(entry.get("scope")),
                    source=source,
                    confidence=self._confidence(entry.get("confidence")),
                    draft_status=DraftStatus.DRAFT,
                    metadata={"session_id": session_id} if session_id else {},
                )
            )
        return items

    @staticmethod
    def _try_parse_json(raw: str) -> list[dict[str, Any]] | None:
        """Parse an LLM response that may be fenced in markdown or loose JSON."""
        text = raw.strip()
        # Strip a markdown code fence if present.
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Attempt to salvage a bare object or the first array.
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                try:
                    data = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    logger.warning("LLM fact extractor returned unparseable output")
                    return None
            else:
                logger.warning("LLM fact extractor returned unparseable output")
                return None
        if not isinstance(data, list):
            return None
        return [e for e in data if isinstance(e, dict)]

    @staticmethod
    def _kind(value: Any) -> MemoryKind:
        try:
            return MemoryKind(str(value).lower())
        except ValueError:
            return MemoryKind.FACT

    @staticmethod
    def _scope(value: Any) -> MemoryScope:
        try:
            return MemoryScope(str(value).lower())
        except ValueError:
            return MemoryScope.USER

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            c = float(value)
        except (TypeError, ValueError):
            return 1.0
        return max(0.0, min(1.0, c))
