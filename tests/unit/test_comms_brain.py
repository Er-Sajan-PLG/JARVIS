"""Tests for JARVIS-tells-me-about-mail: chat context trigger + digest + tools."""

from unittest.mock import AsyncMock, patch

import pytest

from app.adapters.web.router import _wants_email_context
from app.tools import DEFAULT_TOOLSET


class TestWantsEmailContext:
    @pytest.mark.parametrize(
        "message",
        [
            "What important email did I miss?",
            "Any unread emails?",
            "Who emailed me today?",
            "Check my inbox",
            "Summarize my mail",
            "Which senders stand out?",
        ],
    )
    def test_triggers(self, message):
        assert _wants_email_context(message) is True

    @pytest.mark.parametrize(
        "message",
        [
            "Hello JARVIS",
            "Write a poem about blackmail",
            "Remailed the package yesterday",
            "List the files",
        ],
    )
    def test_no_trigger(self, message):
        assert _wants_email_context(message) is False


class TestSummarizeUnread:
    @pytest.mark.asyncio
    async def test_digest_shape(self):
        from app.integrations.email.tools import summarize_unread

        emails = [
            {
                "from": "Payoneer <a@b.c>",
                "subject": "FINAL REMINDER",
                "body": "x",
            },
            {"from": "npm <n@n.com>", "subject": "security", "body": "y"},
        ]
        with patch("app.integrations.email.tools.EmailReader") as reader_cls:
            reader_cls.return_value.get_unread = AsyncMock(return_value=emails)
            reader_cls.return_value.close = AsyncMock()
            digest = await summarize_unread(limit=30)

        assert "UNREAD: 2" in digest
        assert "Payoneer" in digest
        assert "FINAL REMINDER" in digest

    @pytest.mark.asyncio
    async def test_empty_inbox(self):
        from app.integrations.email.tools import summarize_unread

        with patch("app.integrations.email.tools.EmailReader") as reader_cls:
            reader_cls.return_value.get_unread = AsyncMock(return_value=[])
            reader_cls.return_value.close = AsyncMock()
            assert await summarize_unread() == "No unread emails."


class TestCommsToolsRegistered:
    @pytest.mark.parametrize(
        "name",
        [
            "read_emails",
            "search_emails",
            "send_email",
            "reply_email",
            "send_notification",
            "get_brief",
        ],
    )
    def test_registered(self, name):
        assert name in DEFAULT_TOOLSET

    @pytest.mark.asyncio
    async def test_read_emails_tool(self):
        from app.tools.comms_tools import comms_read_emails

        with patch(
            "app.integrations.email.tools.read_emails",
            new=AsyncMock(return_value={"success": True, "emails": [], "count": 0}),
        ):
            out = await comms_read_emails(unread_only=True)
        assert '"count": 0' in out
