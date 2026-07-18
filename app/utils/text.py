"""
Shared text utilities for memory retrieval and ranking.

Both ``app.memory.retrieval.KeywordRetriever`` and
``app.memory.ranking.MemoryRanker`` need stop-word filtering and keyword
extraction. This module is the single source of truth so the two can never
drift apart (previously they each kept their own copy — and the two copies
had *different* stop-word sets, which silently weakened relevance scores).
"""

import re
from typing import Iterable, Set

# Common English stop words. Frozen so it can be shared safely across
# instances and modules without accidental mutation.
STOP_WORDS: frozenset[str] = frozenset({
    'i', 'me', 'my', 'myself', 'we', 'our', 'you', 'your', 'he', 'him',
    'his', 'she', 'her', 'it', 'its', 'they', 'them', 'their', 'what',
    'which', 'who', 'this', 'that', 'these', 'those', 'am', 'is', 'are',
    'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do',
    'does', 'did', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because',
    'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about',
    'against', 'between', 'through', 'during', 'before', 'after', 'to',
    'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under',
    'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where',
    'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some',
    'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
    'too', 'very', 'can', 'will', 'just', 'should', 'now', 'would', 'could',
    'im', 'ive', 'dont', 'doesnt', 'didnt', 'wont', 'cant', 'shouldnt',
})


def extract_keywords(text: str, stop_words: Iterable[str] = STOP_WORDS) -> Set[str]:
    """
    Lowercase, strip punctuation, split, and drop stop words + single chars.

    Shared by retrieval and ranking so query and memory text are tokenized
    **identically**. The previous duplicate implementations diverged: ranking's
    relevance score split memory text on whitespace without punctuation
    stripping, while the query path stripped punctuation first. Using one
    function removes that inconsistency.
    """
    if not text:
        return set()
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    words = text.split()
    stop = set(stop_words)
    return {w for w in words if w not in stop and len(w) > 1}
