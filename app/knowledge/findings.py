"""
Saving important research findings into JARVIS long-term memory.

A "finding" is a notable claim, definition, or result the user wants to
remember across sessions. It is stored via the existing :class:`MemoryManager`
under a dedicated category so it is separable from personal facts:

    category = "finding"
    type     = "paper_note"
    metadata = {
        "source_title": <paper title or filename>,
        "page":         <int, 1-based; 0 if unknown>,
        "doc_id":       <paper store doc_id; "" if unknown>,
    }

The metadata lets the UI later show "where this came from" and (optionally)
deep-link back to the source paper.
"""

from typing import Optional

from app.memory.manager import MemoryManager
from app.memory.schema import Memory, IMPORTANCE_MEDIUM


CATEGORY_FINDING = "finding"
TYPE_PAPER_NOTE = "paper_note"


def save_finding(
    memory_manager: MemoryManager,
    text: str,
    source_meta: Optional[dict] = None,
    importance: float = IMPORTANCE_MEDIUM,
    confidence: float = 1.0,
) -> Optional[Memory]:
    """Persist a research finding into long-term memory.

    Args:
        memory_manager: the JARVIS MemoryManager to store through.
        text:           the finding text (the ``value`` of the memory).
        source_meta:    optional dict with any of:
                          - source_title (str): paper title or filename
                          - page (int): 1-based page number (0 if unknown)
                          - doc_id (str): PaperStore doc_id ("" if unknown)
                        Unknown keys are ignored; missing keys default.
        importance:     memory importance 0.0–1.0 (default medium).
        confidence:     memory confidence 0.0–1.0 (default 1.0).

    Returns:
        The created :class:`Memory`, or ``None`` if ``text`` is empty/blank
        (mirrors MemoryManager returning None for no-op stores).
    """
    if not text or not str(text).strip():
        return None

    # Always normalize (records page:0 when unknown) so provenance is present
    # and consistent even for findings with no explicit source.
    metadata = _normalize_source_meta(source_meta)

    # MemoryManager.store forwards `metadata` from the fact dict into the
    # Memory (appended or replaced), so provenance is set in one call.
    memory = memory_manager.store(
        {
            "category": CATEGORY_FINDING,
            "type": TYPE_PAPER_NOTE,
            "value": str(text).strip(),
            "importance": importance,
            "confidence": confidence,
            "metadata": metadata,
        }
    )

    return memory


def _normalize_source_meta(source_meta: Optional[dict]) -> dict:
    """Extract only the recognized source fields, with safe defaults.

    ``page`` is always present (default 0 = unknown) so provenance metadata is
    consistent whether or not a source was supplied.
    """
    meta: dict = {"page": 0}

    if not isinstance(source_meta, dict):
        return meta

    title = source_meta.get("source_title") or source_meta.get("title")
    if title:
        meta["source_title"] = str(title)

    page = source_meta.get("page", 0)
    try:
        meta["page"] = int(page)
    except (TypeError, ValueError):
        meta["page"] = 0

    doc_id = source_meta.get("doc_id", "")
    if doc_id:
        meta["doc_id"] = str(doc_id)

    return meta
