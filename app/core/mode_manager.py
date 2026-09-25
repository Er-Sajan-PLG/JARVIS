"""Operational mode manager (Migration Plan Step 3).

Holds the active ``BaseMode``, switches between modes, and records transition
history. Step 3 is a facade: nothing calls into LLM paths yet, and every mode
returns today's default prompt, so behavior is unchanged by construction.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.modes.base_mode import BaseMode
from app.modes.evolution_mode import EvolutionMode
from app.modes.maintenance_mode import MaintenanceMode
from app.modes.production_mode import ProductionMode
from app.modes.teacher_mode import TeacherMode

DEFAULT_MODE = "production"


class ModeManager:
    """Owns the active mode and its switch history."""

    def __init__(self, prompts_dir: str = "prompts") -> None:
        self._modes: dict[str, BaseMode] = {
            "production": ProductionMode(prompts_dir=prompts_dir),
            "teacher": TeacherMode(prompts_dir=prompts_dir),
            "maintenance": MaintenanceMode(prompts_dir=prompts_dir),
            "evolution": EvolutionMode(prompts_dir=prompts_dir),
        }
        self._active_name: str = DEFAULT_MODE
        self._history: list[dict[str, str]] = []

    @property
    def active_mode(self) -> BaseMode:
        """Currently active mode instance."""
        return self._modes[self._active_name]

    @property
    def mode_name(self) -> str:
        """Name of the currently active mode."""
        return self._active_name

    @property
    def history(self) -> list[dict[str, str]]:
        """Transition history (copies; oldest first)."""
        return [dict(entry) for entry in self._history]

    def set_mode(self, mode_name: str) -> None:
        """Switch the active mode, recording the transition with a timestamp.

        Raises:
            ValueError: If ``mode_name`` is not a registered mode.
        """
        if mode_name not in self._modes:
            raise ValueError(f"Unknown mode: {mode_name!r} (known: {sorted(self._modes)})")
        previous = self._active_name
        self._active_name = mode_name
        self._history.append(
            {
                "from": previous,
                "to": mode_name,
                "at": datetime.now(UTC).isoformat(),
            }
        )

    def get_system_prompt(self) -> str:
        """System prompt of the active mode."""
        return self.active_mode.system_prompt

    def format_response(self, text: str) -> str:
        """Format a response through the active mode (identity in Step 3)."""
        return self.active_mode.format_response(text)
