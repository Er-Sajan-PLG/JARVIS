"""
Candidate Retrieval for JARVIS v2.0

Finds candidate memories that MIGHT be relevant.
Does NOT rank or score them - that's MemoryRanker's job.
"""

import re
from typing import Protocol

from app.memory.schema import Memory


class CandidateRetriever(Protocol):
    """Protocol for candidate retrieval."""
    
    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]:
        ...
    
    def on_memory_added(self, memory: Memory) -> None:
        ...
    
    def on_memory_removed(self, memory_id: str) -> None:
        ...
    
    def on_index_rebuilt(self, memories: list[Memory]) -> None:
        ...
    
    def clear(self) -> None:
        ...


class KeywordRetriever:
    """Keyword-based candidate retrieval."""
    
    def __init__(self, min_keyword_overlap: int = 1):
        self._memories: list[Memory] = []
        self._min_overlap = min_keyword_overlap
        self._stop_words = self._build_stop_words()
    
    def find_candidates(self, query: str, limit: int = 50) -> list[Memory]:
        if not self._memories or not query:
            return []
        
        query_keywords = self._extract_keywords(query)
        if not query_keywords:
            return []
        
        candidates = []
        for memory in self._memories:
            memory_keywords = self._get_memory_keywords(memory)
            overlap = query_keywords & memory_keywords
            
            if len(overlap) >= self._min_overlap:
                candidates.append(memory)
                if len(candidates) >= limit:
                    break
        
        return candidates
    
    def on_memory_added(self, memory: Memory) -> None:
        if memory not in self._memories:
            self._memories.append(memory)
    
    def on_memory_removed(self, memory_id: str) -> None:
        self._memories = [m for m in self._memories if m.id != memory_id]
    
    def on_index_rebuilt(self, memories: list[Memory]) -> None:
        self._memories = list(memories)
    
    def clear(self) -> None:
        self._memories.clear()
    
    def _extract_keywords(self, text: str) -> set[str]:
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        return {w for w in words if w not in self._stop_words and len(w) > 1}
    
    def _get_memory_keywords(self, memory: Memory) -> set[str]:
        text = f"{memory.value} {memory.category} {memory.memory_type}"
        return self._extract_keywords(text)
    
    def _build_stop_words(self) -> set[str]:
        return {
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
        }