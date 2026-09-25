"""JARVIS Core Package (Migration Plan Step 3).

Central orchestration pieces. Step 3 owns ``mode_manager``.
"""

from app.core.mode_manager import ModeManager

__all__ = ["ModeManager"]
