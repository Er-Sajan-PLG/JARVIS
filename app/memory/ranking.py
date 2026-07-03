"""
Memory Ranking for JARVIS v2.0

Takes candidate memories and ranks them by relevance.
Separate from retrieval - this is where scoring happens.

Ranking factors:
- Relevance: How well the memory matches the query
- Importance: Manually set or inferred importance
- Frequency: How often this memory has been accessed
- Recency: How recently this memory was used/updated
- Confidence: How reliable this memory is
"""

import re
import time
from dataclasses import dataclass
from typing import Optional

from app.memory.schema import Memory, MemoryResult


@dataclass
class RankingWeights:
    """
    Weights for different ranking factors.
    All weights should sum to ~1.0 for interpretable scores.
    """
    relevance: float = 0.35   # Keyword/vector overlap with query
    importance: float = 0.25  # Manually set importance
    frequency: float = 0.15   # Access count (log scale)
    recency: float = 0.15     # Time since last used
    confidence: float = 0.10  # Reliability of the fact


DEFAULT_WEIGHTS = RankingWeights()


class MemoryRanker:
    """
    Ranks candidate memories by their relevance to a query.
    
    Separated from retrieval so you can:
    - Swap ranking algorithms without touching retrieval
    - Tune weights independently
    - Add new ranking signals easily
    """
    
    def __init__(
        self,
        weights: RankingWeights = None,
        recency_half_life_days: float = 7.0,
        frequency_scale: int = 10
    ):
        """
        Args:
            weights: Importance of each ranking factor
            recency_half_life_days: Days for recency to decay by 50%
            frequency_scale: Access count at which frequency_score = 1.0
        """
        self.weights = weights or DEFAULT_WEIGHTS
        self._recency_half_life = recency_half_life_days * 24 * 60 * 60
        self._frequency_scale = frequency_scale
        self._stop_words = self._build_stop_words()
    
    def rank(
        self,
        candidates: list[Memory],
        query: str,
        limit: int = 20,
        min_score: float = 0.0
    ) -> list[MemoryResult]:
        """
        Rank candidates and return top N results.
        
        Args:
            candidates: Memories to rank (from CandidateRetriever)
            query: The original query for relevance scoring
            limit: Maximum results to return
            min_score: Minimum score to include
        
        Returns:
            List of MemoryResult sorted by score (highest first)
        """
        if not candidates:
            return []
        
        query_keywords = self._extract_keywords(query)
        current_time = time.time()
        
        scored = []
        for memory in candidates:
            scores = self._calculate_all_scores(memory, query_keywords, current_time)
            total = self._combine_scores(scores)
            
            if total >= min_score:
                scored.append(MemoryResult(memory=memory, score=total))
        
        # Sort by score descending
        scored.sort(key=lambda x: x.score, reverse=True)
        
        return scored[:limit]
    
    def _calculate_all_scores(
        self,
        memory: Memory,
        query_keywords: set[str],
        current_time: float
    ) -> dict[str, float]:
        """Calculate individual factor scores for a memory"""
        return {
            "relevance": self._score_relevance(memory, query_keywords),
            "importance": self._score_importance(memory),
            "frequency": self._score_frequency(memory),
            "recency": self._score_recency(memory, current_time),
            "confidence": self._score_confidence(memory),
        }
    
    def _combine_scores(self, scores: dict[str, float]) -> float:
        """Combine individual scores using weights"""
        return (
            self.weights.relevance * scores["relevance"] +
            self.weights.importance * scores["importance"] +
            self.weights.frequency * scores["frequency"] +
            self.weights.recency * scores["recency"] +
            self.weights.confidence * scores["confidence"]
        )
    
    def _score_relevance(self, memory: Memory, query_keywords: set[str]) -> float:
        """
        Score based on keyword overlap between query and memory.
        Uses Jaccard-like similarity with category/type boosts.
        """
        if not query_keywords:
            return 0.0
        
        memory_text = f"{memory.value} {memory.category} {memory.memory_type}".lower()
        memory_keywords = set(memory_text.split())
        
        # Remove stop words from memory keywords too
        memory_keywords = memory_keywords - self._stop_words
        
        if not memory_keywords:
            return 0.0
        
        overlap = query_keywords & memory_keywords
        union = query_keywords | memory_keywords
        
        # Jaccard similarity
        jaccard = len(overlap) / len(union) if union else 0.0
        
        # Boost for category/type matches
        category_boost = 0.2 if memory.category in query_keywords else 0.0
        type_boost = 0.15 if memory.memory_type in query_keywords else 0.0
        
        return min(1.0, jaccard + category_boost + type_boost)
    
    def _score_importance(self, memory: Memory) -> float:
        """Direct importance score (0-1)"""
        return memory.importance
    
    def _score_frequency(self, memory: Memory) -> float:
        """
        Normalize access count using log scale.
        Access count of frequency_scale → score of 1.0
        """
        if memory.access_count <= 0:
            return 0.0
        # Log scale: log(1 + count) / log(1 + scale)
        import math
        return min(1.0, math.log(1 + memory.access_count) / math.log(1 + self._frequency_scale))
    
    def _score_recency(self, memory: Memory, current_time: float) -> float:
        """
        Exponential decay based on time since last used.
        Half-life determines how quickly old memories fade.
        """
        age_seconds = current_time - memory.last_used
        if age_seconds <= 0:
            return 1.0
        return 0.5 ** (age_seconds / self._recency_half_life)
    
    def _score_confidence(self, memory: Memory) -> float:
        """Direct confidence score (0-1)"""
        return memory.confidence
    
    def _extract_keywords(self, text: str) -> set[str]:
        """Extract keywords from text"""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        return {w for w in words if w not in self._stop_words and len(w) > 1}
    
    def _build_stop_words(self) -> set[str]:
        """Build stop words set"""
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
        }