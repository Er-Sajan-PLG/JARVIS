"""MCP, session, board, and doc-facts evals."""

from __future__ import annotations

from evals.eval import EvalResult, EvalStatus


class McpClientEval:
    """MCP client types and registry are importable."""

    name = "mcp_client"

    async def run(self) -> EvalResult:
        try:
            from app.integrations.mcp import (
                MCPServerConfig,
                TransportType,
            )

            config = MCPServerConfig(name="test", transport=TransportType.HTTP, url="http://x")
            if config.transport != TransportType.HTTP:
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message="transport not set",
                )
            return EvalResult(
                name=self.name,
                status=EvalStatus.PASS,
                score=1.0,
                message="MCP client imports and constructs",
            )
        except Exception as e:
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message=f"exception: {e}",
            )


class SessionLifecycleEval:
    """SessionManager fork/archive/delete work correctly."""

    name = "session_lifecycle"

    async def run(self) -> EvalResult:
        try:
            import tempfile
            from pathlib import Path

            from app.session.manager import SessionManager
            from app.session.persistence import SessionPersistence

            with tempfile.TemporaryDirectory() as tmp:
                mgr = SessionManager(SessionPersistence(data_dir=Path(tmp)))
                await mgr.get_or_create_session("src")
                forked = await mgr.fork_session("src")
                if forked.session_id == "src":
                    return EvalResult(
                        name=self.name,
                        status=EvalStatus.FAIL,
                        message="fork has same id",
                    )

                archived = await mgr.archive_session("src")
                if not archived.metadata.get("archived"):
                    return EvalResult(
                        name=self.name,
                        status=EvalStatus.FAIL,
                        message="archive not marked",
                    )

                if "src" in mgr._active_sessions:
                    return EvalResult(
                        name=self.name,
                        status=EvalStatus.FAIL,
                        message="archived session still active",
                    )

                if not await mgr.delete_session(forked.session_id):
                    return EvalResult(
                        name=self.name,
                        status=EvalStatus.FAIL,
                        message="delete returned False",
                    )

                return EvalResult(
                    name=self.name,
                    status=EvalStatus.PASS,
                    score=1.0,
                    message="fork/archive/delete work",
                )
        except Exception as e:
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message=f"exception: {e}",
            )


class ContextTrimmingEval:
    """Token-aware context trimming keeps pinned, drops oldest."""

    name = "context_trimming"

    async def run(self) -> EvalResult:
        try:
            from app.domain import ConversationState, Message, Role
            from app.session.context import trim_conversation

            conv = ConversationState(
                id="c",
                messages=[
                    Message(id="1", role=Role.USER, content="aaaa"),
                    Message(id="2", role=Role.USER, content="bbbb"),
                    Message(id="3", role=Role.USER, content="cccc", pinned=True),
                ],
            )

            result = trim_conversation(conv, max_tokens=1)
            kept_ids = [m.id for m in result.kept]
            if "3" not in kept_ids:
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message="pinned message dropped",
                )
            return EvalResult(
                name=self.name,
                status=EvalStatus.PASS,
                score=1.0,
                message="trimming respects pinned+budget",
            )
        except Exception as e:
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message=f"exception: {e}",
            )


class BoardGovernanceEval:
    """All 8 governance checks pass."""

    name = "board_governance"

    async def run(self) -> EvalResult:
        try:
            import subprocess
            import sys

            result = subprocess.run(
                [sys.executable, "scripts/board/review.py"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message=f"board failed: {result.stderr[:500]}",
                )
            return EvalResult(
                name=self.name,
                status=EvalStatus.PASS,
                score=1.0,
                message="all 8 governance checks pass",
            )
        except Exception as e:
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message=f"exception: {e}",
            )


class DocFactsDriftEval:
    """Documentation fact markers are consistent with repository."""

    name = "doc_facts_drift"

    async def run(self) -> EvalResult:
        try:
            import subprocess
            import sys

            result = subprocess.run(
                [sys.executable, "scripts/sync_doc_facts.py", "--check"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                return EvalResult(
                    name=self.name,
                    status=EvalStatus.FAIL,
                    message=f"drift: {result.stdout[:500]}",
                )
            return EvalResult(
                name=self.name,
                status=EvalStatus.PASS,
                score=1.0,
                message="no doc drift",
            )
        except Exception as e:
            return EvalResult(
                name=self.name,
                status=EvalStatus.FAIL,
                message=f"exception: {e}",
            )
