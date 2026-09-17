"""Unit tests for morning brief service."""
import os
from unittest.mock import patch

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
        assert len(brief["sections"]) == 3

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
