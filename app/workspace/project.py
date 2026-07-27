"""Project entity & metadata domain model for workspace management.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Project:
    """Domain model representing an active workspace project."""
    project_id: str
    name: str
    root_path: Path
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def exists(self) -> bool:
        """Check if project root directory exists."""
        return self.root_path.exists() and self.root_path.is_dir()
