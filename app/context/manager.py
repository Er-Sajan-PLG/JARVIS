"""
Context Window Manager for JARVIS v2.0

Key improvement: Trims conversation in user/assistant PAIRS,
not individual messages. This preserves conversational coherence.

Before calling the LLM:
1. Count tokens (using real tokenizer if available)
2. If too large → Trim oldest PAIRS first
3. Never break a user/assistant exchange
"""

from dataclasses import dataclass
from typing import Callable, Optional, List

from app.utils.tokenizer import get_token_counter


@dataclass
class ContextStats:
    """Statistics about the context"""
    total_tokens: int
    max_tokens: int
    utilization: float
    messages_kept: int
    messages_trimmed: int
    pairs_kept: int
    pairs_trimmed: int
    was_trimmed: bool


class ContextWindowManager:
    """
    Manages the context window to never exceed model limits.
    
    Key design: Trims in PAIRS, not individual messages.
    A pair is: [user_message, assistant_message] or a single orphaned message.
    """
    
    # Roles in order for pair detection
    CONVERSATION_ROLES = ("user", "assistant")
    
    def __init__(
        self,
        max_tokens: int = 4096,
        safety_margin: int = 100,
        token_counter: Callable = None,
        estimation_method: str = "auto",
        model_name: str = "default"
    ):
        self.max_tokens = max_tokens
        self.safety_margin = safety_margin
        self.effective_max = max_tokens - safety_margin
        
        if token_counter:
            self._count_tokens = token_counter
        else:
            self._count_tokens = get_token_counter(model_name)
        
        self.last_stats: Optional[ContextStats] = None
    
    @staticmethod
    def _content_to_text(content) -> str:
        """Coerce message content into a token-countable string.

        Guards the real tokenizer (tiktoken/transformers) against unexpected
        content shapes: None -> ""; list (multimodal/tool blocks) -> joined
        text; everything else -> str(...).
        """
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [b.get("text") or "" for b in content if isinstance(b, dict)]
            return "\n".join(p for p in parts if p)
        return str(content)

    def count_tokens(self, messages: list[dict]) -> int:
        """
        Count total tokens in a message list.
        Includes ~4 tokens per message for role/formatting overhead.
        """
        total = 0
        for m in messages:
            # Overhead for role, formatting, etc.
            total += 4
            total += self._count_tokens(self._content_to_text(m.get("content")))
        return total
    
    def count_tokens_text(self, text: str) -> int:
        """Count tokens in a single text string"""
        return self._count_tokens(text)
    
    def fit(self, messages: list[dict], max_tokens: int = None) -> list[dict]:
        """
        Fit messages into the context window, trimming in PAIRS.
        
        Args:
            messages: List of message dicts
            max_tokens: Override max tokens for this call
        
        Returns:
            Fitted message list that fits in context window
        """
        max_tokens = max_tokens or self.effective_max
        original_count = len(messages)
        was_trimmed = False
        
        # Separate system and conversation messages
        system_messages = [m for m in messages if m["role"] == "system"]
        conversation_messages = [m for m in messages if m["role"] != "system"]
        
        system_tokens = self.count_tokens(system_messages)
        available_tokens = max_tokens - system_tokens
        
        # Handle case where system prompt alone exceeds limit
        if available_tokens <= 0:
            self.last_stats = ContextStats(
                total_tokens=system_tokens,
                max_tokens=max_tokens,
                utilization=system_tokens / max_tokens if max_tokens else 0,
                messages_kept=len(system_messages),
                messages_trimmed=original_count - len(system_messages),
                pairs_kept=0,
                pairs_trimmed=0,
                was_trimmed=True,
            )
            return system_messages
        
        # Group conversation messages into pairs
        pairs = self._group_into_pairs(conversation_messages)
        original_pairs = len(pairs)
        
        # Trim pairs from oldest, keeping as many complete pairs as possible
        fitted_pairs: List[List[dict]] = []
        current_tokens = 0
        
        for pair in reversed(pairs):
            pair_tokens = self.count_tokens(pair)
            
            if current_tokens + pair_tokens <= available_tokens:
                fitted_pairs.insert(0, pair)
                current_tokens += pair_tokens
            else:
                was_trimmed = True
                # RISK GUARD: if even the newest pair overflows the window,
                # keep it so the active user prompt is never silently dropped.
                if not fitted_pairs:
                    fitted_pairs.insert(0, pair)
                    current_tokens += pair_tokens
        
        # Flatten pairs back to message list
        fitted_conversation = [msg for pair in fitted_pairs for msg in pair]
        final_messages = system_messages + fitted_conversation
        final_tokens = self.count_tokens(final_messages)
        
        self.last_stats = ContextStats(
            total_tokens=final_tokens,
            max_tokens=max_tokens,
            utilization=final_tokens / max_tokens if max_tokens else 0,
            messages_kept=len(final_messages),
            messages_trimmed=original_count - len(final_messages),
            pairs_kept=len(fitted_pairs),
            pairs_trimmed=original_pairs - len(fitted_pairs),
            was_trimmed=was_trimmed,
        )
        
        return final_messages
    
    def _group_into_pairs(self, messages: list[dict]) -> list[list[dict]]:
        """
        Group messages into user/assistant pairs.
        
        A pair ends when:
        - We see an assistant message (completes the exchange)
        - We see a user message after another user message (orphan)
        - We run out of messages
        
        This ensures we never break a user→assistant exchange.
        """
        if not messages:
            return []
        
        pairs = []
        current_pair = [messages[0]]
        
        for i in range(1, len(messages)):
            msg = messages[i]
            prev_msg = messages[i - 1]
            
            current_pair.append(msg)
            
            # End pair after assistant message
            # Or if we have two consecutive user messages (orphan the first)
            if msg["role"] == "assistant":
                pairs.append(current_pair)
                current_pair = []
            elif msg["role"] == "user" and prev_msg["role"] == "user":
                # Two consecutive user messages - first one is orphaned
                pairs.append(current_pair[:-1])
                current_pair = [msg]
        
        # Handle any remaining messages
        if current_pair:
            pairs.append(current_pair)
        
        return pairs
    
    def get_stats(self) -> Optional[ContextStats]:
        """Get stats from the last fit() call"""
        return self.last_stats
    
    def get_tokenizer_info(self) -> dict:
        """Get information about the active tokenizer"""
        from app.utils.tokenizer import get_tokenizer_info
        return get_tokenizer_info()
