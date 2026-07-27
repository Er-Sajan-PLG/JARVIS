"""JARVIS Workspace Package.

Provides active project workspace management, filesystem watchers, and ContentSource integration.
"""

from app.workspace.manager import WorkspaceManager
from app.workspace.project import Project
from app.workspace.watcher import FileWatcher

__all__ = [
    "Project",
    "FileWatcher",
    "WorkspaceManager",
]
