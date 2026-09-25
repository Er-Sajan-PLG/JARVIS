"""Evolution mode stub (Migration Plan Step 3).

Self-evaluation mode (future). Step 3: returns today's default prompt so
switching to it changes nothing.
"""

from __future__ import annotations

from app.modes.base_mode import BaseMode
from app.modes.default_prompt import default_system_prompt


class EvolutionMode(BaseMode):
    """Self-evaluation and optimization mode (stub: default prompt)."""

    def __init__(self, prompts_dir: str = "prompts") -> None:
        self._prompts_dir = prompts_dir

    @property
    def name(self) -> str:
        return "evolution"

    @property
    def emoji(self) -> str:
        return "🧬"

    @property
    def system_prompt(self) -> str:
        return default_system_prompt(self._prompts_dir)
