"""
Retrieval-augmented generation over ingested papers.

:func:`answer` retrieves relevant chunks from a :class:`PaperStore`, builds a
grounded prompt that asks the model to cite sources as ``[title, p.X]``, calls
the supplied ``model_client.generate``, and returns the answer together with
the source chunks so the UI can render clickable citations.

The function is intentionally framework-agnostic: it only depends on the
:class:`PaperStore` search surface and the project-wide ``ModelClient``
Protocol (``generate(messages: list[dict], **kwargs) -> ModelResponse`` with a
``.content`` string). This keeps it unit-testable with a stub client.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Protocol


class ModelClient(Protocol):
    """Minimal structural type for the LLM client used by JARVIS.

    Mirrors ``app/models/client.py`` — only the bits RAG needs.
    """

    def generate(self, messages: list[dict], **kwargs) -> "object":
        ...


@dataclass
class RAGResult:
    """Result of a RAG query.

    ``answer``  — model-generated, citation-grounded text.
    ``sources`` — the retrieved chunks (each a dict with doc_id, filename,
                  title, page, chunk_index, text) in relevance order, so the
                  UI can render clickable ``[title, p.X]`` references.
    """

    answer: str
    sources: List[dict] = field(default_factory=list)


# ── Prompt construction ─────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are JARVIS's research assistant. Answer the user's question using "
    "ONLY the retrieved excerpts below. If the excerpts do not contain enough "
    "information to answer, say so honestly and do not invent facts.\n"
    "Cite every claim with the marker [title, p.X] where title is the source "
    "paper title and X is the page number shown in the excerpts. Place the "
    "citation right after the sentence it supports. Keep the answer concise "
    "and factual."
)


def _format_context(sources: List[dict]) -> str:
    """Render retrieved chunks as numbered excerpts with citation markers."""
    if not sources:
        return "(no excerpts retrieved)"

    lines = []
    for i, src in enumerate(sources, start=1):
        title = src.get("title") or src.get("filename") or "unknown"
        page = src.get("page", 0)
        text = (src.get("text") or "").strip()
        lines.append(f"[{i}] {title}, p.{page}\n{text}")
    return "\n\n".join(lines)


def _citation_for(src: dict) -> str:
    title = src.get("title") or src.get("filename") or "unknown"
    page = src.get("page", 0)
    return f"[{title}, p.{page}]"


# ── Public API ──────────────────────────────────────────────────────────────

def answer(
    query: str,
    model_client: ModelClient,
    store,
    limit: int = 6,
    system_prompt: Optional[str] = None,
) -> RAGResult:
    """Answer ``query`` using retrieved paper chunks.

    Args:
        query:        the user's natural-language question.
        model_client: any object with ``generate(messages, **kwargs)`` returning
                      an object exposing ``.content`` (str).
        store:        a :class:`PaperStore` (or anything with a ``search`` method).
        limit:        max chunks to retrieve (defaults to 6).
        system_prompt: optional override for the grounding system prompt.

    Returns:
        RAGResult(answer, sources). When nothing is retrieved, ``answer``
        explains that no relevant excerpts were found and ``sources`` is empty.
    """
    query = (query or "").strip()
    if not query:
        return RAGResult(answer="Please provide a question to answer.", sources=[])

    sources = store.search(query, limit=limit) if limit > 0 else []
    if not sources:
        return RAGResult(
            answer=(
                "I couldn't find any relevant excerpts in the ingested papers "
                "to answer that. Try ingesting related PDFs or rephrasing."
            ),
            sources=[],
        )

    context = _format_context(sources)
    sys_msg = system_prompt or _SYSTEM_PROMPT
    user_msg = f"Retrieved excerpts:\n\n{context}\n\nQuestion: {query}"

    response = model_client.generate(
        [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ]
    )

    # Tolerate either a ModelResponse-like object or a plain string.
    answer_text = getattr(response, "content", None)
    if answer_text is None:
        answer_text = str(response) if response is not None else ""

    return RAGResult(answer=answer_text.strip(), sources=sources)
