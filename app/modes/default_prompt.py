"""Today's-default prompt helper (Migration Plan Step 3).

Single source of truth for "the prompt JARVIS uses today": render
``prompts/system_base.md`` through the existing ``ContextBuilder`` for the
default session (``session_id="default_session"`` — the same default the HTTP
adapter uses at ``app/adapters/http/router.py:83``). Every mode delegates here,
so zero prompt drift holds by construction, not by copy-paste.
"""

from __future__ import annotations

from app.context.builder import ContextBuilder
from app.domain import SessionState
from app.prompt.loader import PromptLoader

DEFAULT_SESSION_ID = "default_session"


def default_system_prompt(prompts_dir: str = "prompts") -> str:
    """Render today's default system prompt via the existing pipeline."""
    builder = ContextBuilder(prompt_loader=PromptLoader(prompts_dir=prompts_dir))
    session = SessionState(session_id=DEFAULT_SESSION_ID)
    prompt: str = builder.build_system_prompt(session)
    return prompt
