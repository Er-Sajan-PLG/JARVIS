"""Production mode (Migration Plan Step 3).

Execution-focused mode. Step 3: ``system_prompt`` returns today's default base
prompt via the shared helper — zero drift by construction.
"""

from __future__ import annotations

from app.modes.base_mode import BaseMode
from app.modes.default_prompt import default_system_prompt


class ProductionMode(BaseMode):
    """High-density, execution-focused mode (facade: default prompt for now)."""

    def __init__(self, prompts_dir: str = "prompts") -> None:
        self._prompts_dir = prompts_dir

    @property
    def name(self) -> str:
        return "production"

    @property
    def emoji(self) -> str:
        return "⚡"

    @property
    def system_prompt(self) -> str:
        return default_system_prompt(self._prompts_dir)
