"""
Prompt Builder for JARVIS v2.0

Assembles prompts in the correct order:
1. System Prompt (with memories embedded)
2. Recent Conversation
3. Current Prompt (if not already in conversation)

Interface:
    prompt_builder.build(memories, conversation, user_prompt)
"""

from app.memory.schema import MemoryResult


class PromptBuilder:
    """
    Assembles prompts from multiple sources in fixed order.
    
    Note: Combines system prompt and memories into a SINGLE system message
    for maximum model compatibility.
    """
    
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
    
    def build(
        self,
        memories: list[MemoryResult] = None,
        conversation: list[dict] = None,
        user_prompt: str = "",
        past_exchanges: list[dict] = None, 
    ) -> list[dict]:
        """
        Build the complete message list for the LLM.
        
        Args:
            memories: Retrieved memories (from memory.retrieve())
            conversation: Recent conversation messages
            user_prompt: The current user message (if not in conversation)
        
        Returns:
            List of message dicts in OpenAI format
        """
        # Build system content (single message for compatibility)
        system_parts = [self.system_prompt]
        
        if past_exchanges:
            past_text = self._format_past_exchanges(past_exchanges)
            if past_text:
                system_parts.append(past_text)

        if memories:
            memories_text = self._format_memories(memories)
            if memories_text:
                system_parts.append(memories_text)
        
        messages = [
            {"role": "system", "content": "\n\n".join(system_parts)}
        ]
        
        # Add conversation history
        if conversation:
            messages.extend(conversation)
        
        # Add current user prompt if not already in conversation
        if user_prompt:
            if not conversation or conversation[-1].get("content") != user_prompt:
                messages.append({
                    "role": "user",
                    "content": user_prompt,
                })
        
        return messages

    def _format_past_exchanges(self, exchanges: list[dict]) -> str:
        """Format past exchanges for inclusion in system prompt"""
        if not exchanges:
            return ""
        
        lines = ["## Relevant Past Exchanges"]
        lines.append("Earlier conversation that may be relevant:")
        lines.append("")
        
        for exchange in exchanges:
            user_msg = exchange.get("user", "").strip()
            assistant_msg = exchange.get("assistant", "").strip()
            lines.append(f"- User: {user_msg}")
            lines.append(f"  Assistant: {assistant_msg}")
        
        return "\n".join(lines)
    
    def _format_memories(self, memories: list[MemoryResult]) -> str:
        """Format retrieved memories for inclusion in prompt"""
        if not memories:
            return ""
        
        lines = ["## Known User Facts"]
        lines.append("Use these facts when relevant to the conversation:")
        lines.append("")
        
        for result in memories:
            memory = result.memory
            lines.append(f"- [{memory.category}] {memory.memory_type}: {memory.value}")
        
        return "\n".join(lines)
    
    def build_with_stats(
        self,
        memories: list[MemoryResult] = None,
        conversation: list[dict] = None,
        user_prompt: str = ""
    ) -> tuple[list[dict], dict]:
        """
        Build messages and return stats about what was included.
        
        Returns:
            Tuple of (messages, stats_dict)
        """
        stats = {
            "system_tokens_estimate": len(self.system_prompt) // 4,
            "memories_included": len(memories) if memories else 0,
            "conversation_messages": len(conversation) if conversation else 0,
            "has_explicit_user_prompt": bool(user_prompt),
        }
        
        messages = self.build(memories, conversation, user_prompt)
        return messages, stats