"""File system watcher for tracking active workspace file changes."""

import logging
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

FileChangeCallback = Callable[[Path, str], None]


class FileWatcher:
    """Monitors workspace directories for file creation, modification, and deletion events."""

    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path)
        self._callbacks: list[FileChangeCallback] = []
        self._is_watching = False

    def register_callback(self, callback: FileChangeCallback) -> None:
        """Register a callback for file system change events."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def scan_changes(self) -> list[tuple[Path, str]]:
        """Perform a scan of the root path returning modified files."""
        changes: list[tuple[Path, str]] = []
        if not self.root_path.exists():
            return changes

        # Simple file scan
        for p in self.root_path.rglob("*"):
            if p.is_file() and not any(part.startswith(".") for part in p.parts):
                changes.append((p, "modified"))
        return changes
