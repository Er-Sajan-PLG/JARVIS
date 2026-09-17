"""Workspace Manager.

Manages active project context, directory scanning, and content source
abstraction for workspace files.
"""

import logging
from pathlib import Path
from typing import Any

from app.domain import ContentSource, ContentType
from app.workspace.project import Project
from app.workspace.watcher import FileWatcher

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Manages active projects and transforms workspace files into ContentSource instances."""

    def __init__(self, workspace_root: str | Path = ".") -> None:
        self.root_path = Path(workspace_root).resolve()
        self.active_project = Project(
            project_id="default_project",
            name=self.root_path.name or "JARVIS Workspace",
            root_path=self.root_path,
        )
        self.watcher = FileWatcher(self.root_path)

    def set_active_project(self, project_path: str | Path, name: str | None = None) -> Project:
        """Switch active workspace project."""
        p = Path(project_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Project path does not exist: {p}")

        proj_id = f"proj-{p.name.lower().replace(' ', '_')}"
        self.active_project = Project(
            project_id=proj_id,
            name=name or p.name,
            root_path=p,
        )
        self.watcher = FileWatcher(p)
        logger.info("Active workspace switched to project '%s' (%s)", self.active_project.name, p)
        return self.active_project

    def get_file_content_source(self, relative_or_abs_path: str | Path) -> ContentSource:
        """Read a workspace file and wrap it in a ContentSource domain entity.

        Args:
            relative_or_abs_path: File path relative to project root or absolute.

        Returns:
            ContentSource domain instance.

        Raises:
            FileNotFoundError: If target file does not exist.
        """
        path = Path(relative_or_abs_path)
        if not path.is_absolute():
            path = self.active_project.root_path / path

        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Workspace file not found: {path}")

        try:
            raw_text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.warning("Error reading file %s: %s", path, e)
            raw_text = ""

        content_type = self._detect_type(path)
        rel_path = (
            path.relative_to(self.active_project.root_path)
            if path.is_relative_to(self.active_project.root_path)
            else path.name
        )

        return ContentSource(
            source_id=f"ws-{hash(str(path)) & 0xFFFFFFFF}",
            content_type=content_type,
            uri=f"file://{path.absolute()}",
            title=str(rel_path),
            raw_text=raw_text,
            metadata={"file_size": path.stat().st_size, "extension": path.suffix},
        )

    def list_files(self, extension_filter: list[str] | None = None) -> list[Path]:
        """List tracked files in active workspace project."""
        files: list[Path] = []
        if not self.active_project.exists():
            return files

        for p in self.active_project.root_path.rglob("*"):
            if p.is_file() and not any(part.startswith(".") for part in p.parts):
                if extension_filter:
                    if p.suffix.lower() in [ext.lower() for ext in extension_filter]:
                        files.append(p)
                else:
                    files.append(p)
        return files

    def _detect_type(self, path: Path) -> ContentType:
        """Detect ContentType based on file extension."""
        ext = path.suffix.lower()
        if ext in (".py", ".js", ".ts", ".html", ".css", ".go", ".rs", ".c", ".cpp", ".java"):
            return ContentType.CODE
        if ext in (".pdf",):
            return ContentType.PDF
        if ext in (".png", ".jpg", ".jpeg", ".webp"):
            return ContentType.IMAGE
        return ContentType.TEXT

    # ── Workspace awareness: git state + file tree ───────────────────────────

    def get_git_state(self) -> dict[str, Any]:
        """Return current git state of the workspace (HEAD, branch, status)."""
        import subprocess

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", "--branch"],
                cwd=self.root_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            lines = result.stdout.strip().splitlines() if result.stdout.strip() else []
            branch_line = next((ln for ln in lines if ln.startswith("##")), "")
            branch = branch_line.replace("## ", "").split("...")[0] if branch_line else "unknown"
            dirty_files = [ln for ln in lines if not ln.startswith("##")]

            head_result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self.root_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            head = head_result.stdout.strip() or "unknown"

            return {
                "head": head,
                "branch": branch,
                "dirty": len(dirty_files) > 0,
                "dirty_files": dirty_files,
            }
        except Exception:
            return {"head": "unknown", "branch": "unknown", "dirty": False, "dirty_files": []}

    def get_file_tree(self, max_depth: int = 3) -> list[dict[str, Any]]:
        """Return a tree of files up to ``max_depth`` levels deep."""
        tree: list[dict[str, Any]] = []
        for p in sorted(self.root_path.rglob("*")):
            try:
                rel = p.relative_to(self.root_path)
            except ValueError:
                continue
            depth = len(rel.parts) - 1
            if depth > max_depth:
                continue
            if p.is_file() and not any(part.startswith(".") for part in rel.parts):
                tree.append(
                    {
                        "path": str(rel),
                        "name": p.name,
                        "depth": depth,
                        "size": p.stat().st_size,
                        "extension": p.suffix.lower(),
                    }
                )
        return tree
