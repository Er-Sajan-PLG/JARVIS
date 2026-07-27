"""ContextBuilder: Assembles System Prompts, Memory, Tokens, History & ContentSources.

Dynamically constructs model context payloads from ContentSource instances, persistent memory records,
and conversation histories within strict model token budgets.
"""

import logging

from app.domain import ContentSource, ConversationState, MemoryRecord, Message, Role, SessionState
from app.prompt.loader import PromptLoader
from app.utils.tokenizer import count_tokens

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Assembles prompt contexts respecting model token budget limits."""

    def __init__(self, prompt_loader: PromptLoader | None = None) -> None:
        self.prompt_loader = prompt_loader or PromptLoader()

    def build_system_prompt(
        self,
        session: SessionState,
        assistant_name: str = "JARVIS",
    ) -> str:
        """Render system base prompt template with session context.

        Args:
            session: Active SessionState.
            assistant_name: Name of AI assistant.

        Returns:
            Rendered system prompt string.
        """
        prefs = session.preferences
        return self.prompt_loader.render(
            "system_base.md",
            assistant_name=assistant_name,
            user_id=session.user_id,
            session_id=session.session_id,
            theme=prefs.theme,
            custom_instructions=prefs.custom_instructions or "None",
        )

    def assemble_context(
        self,
        session: SessionState,
        conversation: ConversationState,
        sources: list[ContentSource] | None = None,
        memories: list[MemoryRecord] | None = None,
        max_context_tokens: int = 8192,
    ) -> list[dict[str, str]]:
        """Assemble full message list for LLM call, ensuring token budget is respected.

        Args:
            session: Active user session.
            conversation: Conversation thread.
            sources: ContentSources (file attachments, workspace docs).
            memories: Retrieved persistent memories.
            max_context_tokens: Max allowed token budget.

        Returns:
            List of message dicts `{"role": ..., "content": ...}` ready for LLM client.
        """
        sources = sources or []
        memories = memories or []

        # 1. System Base Prompt
        system_text = self.build_system_prompt(session)

        # 2. Append Retrieved Memories Block
        if memories:
            mem_text = "\n\n### Relevant User Memories:\n" + "\n".join(
                f"- [{m.category}] {m.key}: {m.value}" for m in memories
            )
            system_text += mem_text

        # 3. Append ContentSources Block
        if sources:
            source_text = "\n\n### Context Documents & Files:\n"
            for src in sources:
                source_text += f"\n--- Document: {src.title} ({src.uri}) ---\n{src.raw_text[:4000]}\n"
            system_text += source_text

        messages_payload: list[dict[str, str]] = [
            {"role": Role.SYSTEM.value, "content": system_text}
        ]

        # 4. Truncate conversation history to fit remaining token budget
        system_tokens = count_tokens(system_text)
        budget_remaining = max(1000, max_context_tokens - system_tokens - 1000)

        accumulated_history: list[dict[str, str]] = []
        accumulated_tokens = 0

        # Process messages from newest to oldest
        for msg in reversed(conversation.messages):
            msg_role = msg.role.value if isinstance(msg.role, Role) else msg.role
            msg_dict = {"role": msg_role, "content": msg.content}
            msg_tokens = count_tokens(msg.content)

            if accumulated_tokens + msg_tokens > budget_remaining:
                logger.info("ContextBuilder truncated conversation history at %d tokens", accumulated_tokens)
                break

            accumulated_history.append(msg_dict)
            accumulated_tokens += msg_tokens

        # Restore chronological order
        messages_payload.extend(reversed(accumulated_history))
        logger.debug("Assembled %d messages (%d tokens total)", len(messages_payload), system_tokens + accumulated_tokens)
        return messages_payload
