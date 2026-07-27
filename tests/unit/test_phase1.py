"""Unit and integration tests for Phase 1: ArtifactManager, WorkspaceManager, SessionPersistence, SessionManager.
"""

from pathlib import Path
import tempfile
import pytest

from app.artifacts.manager import ArtifactManager
from app.domain import ContentType, Role
from app.session.manager import SessionManager
from app.session.persistence import SessionPersistence
from app.workspace.manager import WorkspaceManager


def test_artifact_manager_spill_bytes() -> None:
    """Verify ArtifactManager spills binary data to disk and returns ArtifactHandle."""
    with tempfile.TemporaryDirectory() as td:
        am = ArtifactManager(storage_dir=td)
        handle = am.spill_bytes(
            content_bytes=b"Hello JARVIS Artifacts!",
            filename="test.txt",
            mime_type="text/plain",
        )

        assert handle.title == "test.txt"
        assert handle.byte_size == len(b"Hello JARVIS Artifacts!")
        assert handle.spilled_to_disk is True
        assert Path(handle.file_path).exists()
        assert am.get_artifact_bytes(handle) == b"Hello JARVIS Artifacts!"


def test_workspace_manager_content_source() -> None:
    """Verify WorkspaceManager converts workspace file into ContentSource."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        test_file = root / "script.py"
        test_file.write_text("print('hello')", encoding="utf-8")

        wm = WorkspaceManager(workspace_root=root)
        cs = wm.get_file_content_source("script.py")

        assert cs.title == "script.py"
        assert cs.content_type == ContentType.CODE
        assert "print('hello')" in cs.raw_text
        assert cs.token_estimate >= 1


def test_session_manager_and_persistence() -> None:
    """Verify SessionManager and SessionPersistence save/load session and conversation states."""
    import asyncio

    async def _run() -> None:
        with tempfile.TemporaryDirectory() as td:
            pers = SessionPersistence(data_dir=td)
            sm = SessionManager(persistence=pers)

            session = await sm.get_or_create_session("sess_test_1")
            assert session.session_id == "sess_test_1"

            conv = await sm.get_or_create_conversation(conversation_id="conv_test_1", session_id="sess_test_1")
            assert conv.id == "conv_test_1"

            from app.domain import Message
            conv.add_message(Message(id="msg_1", role=Role.USER, content="Hello server!"))
            await pers.save_conversation(conv)

            reloaded = await pers.load_conversation("conv_test_1")
            assert reloaded is not None
            assert len(reloaded.messages) == 1
            assert reloaded.messages[0].content == "Hello server!"

    asyncio.run(_run())
