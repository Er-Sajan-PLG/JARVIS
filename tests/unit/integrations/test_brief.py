"""Unit tests for morning brief service."""
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.integrations.brief import BriefConfig, BriefService


@pytest.fixture
def config():
    return BriefConfig(
        enabled=True,
        time="08:00",
        delivery_channels=["slack"],
        slack_webhook="https://hooks.slack.com/test",
        email_recipient="test@example.com",
    )


@pytest.fixture
def service(config):
    return BriefService(config)


class TestBriefConfig:
    def test_default_config(self):
        config = BriefConfig()
        assert config.enabled is False
        assert config.time == "08:00"
        assert "slack" in config.delivery_channels

    def test_config_from_env(self):
        with patch.dict(os.environ, {
            "JARVIS_BRIEF_ENABLED": "true",
            "JARVIS_BRIEF_TIME": "09:00",
            "JARVIS_BRIEF_DELIVERY": "slack,email",
        }):
            config = BriefConfig.from_env()
            assert config.enabled is True
            assert config.time == "09:00"
            assert "slack" in config.delivery_channels
            assert "email" in config.delivery_channels


class TestBriefService:
    def test_get_greeting_morning(self, service):
        with patch("app.integrations.brief.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 9
            assert "morning" in service._get_greeting().lower()

    def test_get_greeting_afternoon(self, service):
        with patch("app.integrations.brief.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 14
            assert "afternoon" in service._get_greeting().lower()

    @pytest.mark.asyncio
    async def test_generate_brief(self, service):
        brief = await service.generate_brief()
        assert "greeting" in brief
        assert "sections" in brief
        assert len(brief["sections"]) == 4

    def test_format_brief_text(self, service):
        brief = {
            "greeting": "Good morning.",
            "sections": [
                {"title": "Memory", "content": "5 memories stored."},
                {"title": "Approvals", "content": "No pending approvals."},
            ],
        }
        text = service._format_brief_text(brief)
        assert "Good morning" in text
        assert "Memory" in text
        assert "5 memories stored" in text


class TestEnrichedBrief:
    @pytest.mark.asyncio
    async def test_brief_has_email_section(self):
        from app.integrations.brief import BriefConfig, BriefService

        service = BriefService(BriefConfig(enabled=True))
        with (
            patch("app.integrations.email.client.configured_accounts", return_value=[""]),
            patch(
                "app.integrations.email.tools.summarize_unread",
                new=AsyncMock(return_value="UNREAD: 3\n- Payoneer: reminder"),
            ),
        ):
            brief = await service.generate_brief()
        email = [s for s in brief["sections"] if s["title"] == "Email"]
        assert email
        assert "[primary]" in email[0]["content"]

    @pytest.mark.asyncio
    async def test_brief_email_failure_degrades(self):
        from app.integrations.brief import BriefConfig, BriefService

        service = BriefService(BriefConfig(enabled=True))
        with (
            patch("app.integrations.email.client.configured_accounts", return_value=[""]),
            patch(
                "app.integrations.email.tools.summarize_unread",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            brief = await service.generate_brief()
        email = [s for s in brief["sections"] if s["title"] == "Email"]
        assert "unavailable" in email[0]["content"]


class TestTelegramBriefDelivery:
    @pytest.mark.asyncio
    async def test_telegram_channel(self):
        from app.integrations.brief import BriefConfig, BriefService

        service = BriefService(BriefConfig(delivery_channels=["telegram"]))
        with patch(
            "app.integrations.telegram.send_voice", new=AsyncMock(return_value=True)
        ):
            result = await service.deliver({"greeting": "hi", "sections": []})
        assert result["telegram"]["success"] is True


class TestDeliverScript:
    def test_script_exists(self):
        assert (Path(__file__).resolve().parents[3] / "scripts" / "deliver_brief.py").is_file()
