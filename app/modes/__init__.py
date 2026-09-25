"""JARVIS Modes Package (Migration Plan Step 3).

Operational modes sharing one contract (``BaseMode``). Zero behavior change:
every mode's ``system_prompt`` delegates to the existing rendering path
(``ContextBuilder.build_system_prompt`` over ``prompts/system_base.md``), so
switching modes changes nothing in prompt output yet.
"""

from app.modes.base_mode import BaseMode
from app.modes.evolution_mode import EvolutionMode
from app.modes.maintenance_mode import MaintenanceMode
from app.modes.production_mode import ProductionMode
from app.modes.teacher_mode import TeacherMode

__all__ = [
    "BaseMode",
    "EvolutionMode",
    "MaintenanceMode",
    "ProductionMode",
    "TeacherMode",
]
