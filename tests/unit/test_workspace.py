"""Unit tests for app/workspace: Project, WorkspaceManager, FileWatcher."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.domain import ContentType
from app.workspace.manager import WorkspaceManager
from app.workspace.project import Project
from app.workspace.watcher import FileWatcher


def test_project_entity(tmp_path: Path) -> None:
    non_existent = tmp_path / "missing"
    proj = Project(project_id="p1", name="Missing Proj", root_path=non_existent)
    assert not proj.exists()

    existing_dir = tmp_path / "valid_dir"
    existing_dir.mkdir()
    proj_valid = Project(project_id="p2", name="Valid Proj", root_path=existing_dir)
    assert proj_valid.exists()

    file_path = tmp_path / "file.txt"
    file_path.write_text("hello", encoding="utf-8")
    proj_file = Project(project_id="p3", name="File Proj", root_path=file_path)
    assert not proj_file.exists()


def test_workspace_manager_set_active_project(tmp_path: Path) -> None:
    mgr = WorkspaceManager(workspace_root=tmp_path)
    assert mgr.active_project.root_path == tmp_path.resolve()

    sub_proj = tmp_path / "my_project"
    sub_proj.mkdir()

    # Successful switch
    active = mgr.set_active_project(sub_proj, name="Custom Name")
    assert active.name == "Custom Name"
    assert active.project_id == "proj-my_project"
    assert mgr.active_project.root_path == sub_proj.resolve()
    assert mgr.watcher.root_path == sub_proj.resolve()

    # Missing project path raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        mgr.set_active_project(tmp_path / "non_existent_folder")


def test_workspace_manager_get_file_content_source(tmp_path: Path) -> None:
    mgr = WorkspaceManager(workspace_root=tmp_path)

    # 1. Code file
    py_file = tmp_path / "main.py"
    py_file.write_text("print('hello')", encoding="utf-8")
    cs_py = mgr.get_file_content_source("main.py")
    assert cs_py.content_type == ContentType.CODE
    assert cs_py.title == "main.py"
    assert cs_py.raw_text == "print('hello')"
    assert cs_py.metadata["extension"] == ".py"
    assert cs_py.metadata["file_size"] > 0

    # 2. PDF file
    pdf_file = tmp_path / "doc.pdf"
    pdf_file.write_bytes(b"%PDF-1.5 test content")
    cs_pdf = mgr.get_file_content_source(pdf_file.resolve())
    assert cs_pdf.content_type == ContentType.PDF

    # 3. Image file
    img_file = tmp_path / "pic.png"
    img_file.write_bytes(b"\x89PNG test image")
    cs_img = mgr.get_file_content_source("pic.png")
    assert cs_img.content_type == ContentType.IMAGE

    # 4. Text file
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("Some notes", encoding="utf-8")
    cs_txt = mgr.get_file_content_source("notes.txt")
    assert cs_txt.content_type == ContentType.TEXT

    # 5. Missing file raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        mgr.get_file_content_source("not_found.py")

    # 6. Directory raises FileNotFoundError
    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        mgr.get_file_content_source("sub")


def test_workspace_manager_read_error_fallback(tmp_path: Path) -> None:
    mgr = WorkspaceManager(workspace_root=tmp_path)
    test_file = tmp_path / "error.txt"
    test_file.write_text("data", encoding="utf-8")

    with patch.object(Path, "read_text", side_effect=OSError("Read error")):
        cs = mgr.get_file_content_source("error.txt")
        assert cs.raw_text == ""


def test_workspace_manager_list_files(tmp_path: Path) -> None:
    mgr = WorkspaceManager(workspace_root=tmp_path)

    # Create files
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")

    # Hidden file & dir
    hidden_dir = tmp_path / ".git"
    hidden_dir.mkdir()
    (hidden_dir / "config").write_text("config", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")

    # List all
    all_files = mgr.list_files()
    filenames = [p.name for p in all_files]
    assert "a.py" in filenames
    assert "b.txt" in filenames
    assert ".env" not in filenames
    assert "config" not in filenames

    # List with extension filter
    py_files = mgr.list_files(extension_filter=[".py"])
    assert len(py_files) == 1
    assert py_files[0].name == "a.py"

    # Missing project root
    mgr.active_project.root_path = tmp_path / "gone"
    assert mgr.list_files() == []


def test_file_watcher(tmp_path: Path) -> None:
    watcher = FileWatcher(root_path=tmp_path)

    callbacks_called: list[str] = []

    def cb(path: Path, event: str) -> None:
        callbacks_called.append(f"{event}:{path.name}")

    watcher.register_callback(cb)
    # Duplicate registration should be ignored
    watcher.register_callback(cb)
    assert len(watcher._callbacks) == 1

    (tmp_path / "file1.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / ".hidden").write_text("secret", encoding="utf-8")

    changes = watcher.scan_changes()
    changed_names = [p.name for p, status in changes]
    assert "file1.py" in changed_names
    assert ".hidden" not in changed_names

    # Missing root path returns empty list
    missing_watcher = FileWatcher(root_path=tmp_path / "missing_dir")
    assert missing_watcher.scan_changes() == []
