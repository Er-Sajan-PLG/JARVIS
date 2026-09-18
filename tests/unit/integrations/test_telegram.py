"""Unit tests for the Telegram two-way integration."""

from unittest.mock import AsyncMock, patch

import pytest

from app.integrations.telegram import (
    TelegramConfig,
    TelegramPoller,
    send_message,
)


@pytest.fixture()
def config():
    return TelegramConfig(
        token="test-token",
        allowed_chat_ids=["111", "222"],
        enabled=True,
    )


class TestTelegramConfig:
    def test_ready_when_token_and_enabled(self, config):
        assert config.ready is True

    def test_not_ready_without_token(self):
        assert TelegramConfig(token="", enabled=True).ready is False

    def test_not_ready_when_disabled(self):
        assert TelegramConfig(token="x", enabled=False).ready is False

    def test_legacy_token_env_fallback(self):
        with patch.dict(
            __import__("os").environ,
            {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_API_KEYS": "legacy-token"},
            clear=False,
        ):
            assert TelegramConfig.from_env().token == "legacy-token"

    def test_allowed_ids_parsed(self):
        with patch.dict(
            __import__("os").environ,
            {"TELEGRAM_ALLOWED_CHAT_IDS": "111, 222 "},
            clear=False,
        ):
            assert TelegramConfig.from_env().allowed_chat_ids == ["111", "222"]


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_no_token_skips(self):
        ok = await send_message("hi", config=TelegramConfig(token=""))
        assert ok is False

    @pytest.mark.asyncio
    async def test_no_chat_available_skips(self, config):
        config.allowed_chat_ids = []
        ok = await send_message("hi", config=config)
        assert ok is False


class TestPoller:
    @pytest.mark.asyncio
    async def test_ignores_unknown_chat(self, config):
        poller = TelegramPoller(config)
        with patch(
            "app.integrations.telegram.send_message",
            new=AsyncMock(return_value=True),
        ) as sender:
            await poller._handle_update({"message": {"chat": {"id": 999}, "text": "hello"}})
        sender.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_non_text(self, config):
        poller = TelegramPoller(config)
        with patch(
            "app.integrations.telegram.send_message",
            new=AsyncMock(return_value=True),
        ) as sender:
            await poller._handle_update({"message": {"chat": {"id": 111}}})
        sender.assert_not_called()

    @pytest.mark.asyncio
    async def test_answers_allowed_chat(self, config):
        poller = TelegramPoller(config)
        with (
            patch.object(poller, "_answer", new=AsyncMock(return_value="hello back")),
            patch(
                "app.integrations.telegram.send_message",
                new=AsyncMock(return_value=True),
            ) as sender,
        ):
            await poller._handle_update(
                {
                    "message": {
                        "chat": {"id": 111},
                        "message_id": 7,
                        "text": "hello",
                    }
                }
            )
        sender.assert_called_once()
        args, kwargs = sender.call_args
        assert args[0] == "hello back"
        assert kwargs["chat_id"] == "111"
        assert kwargs["reply_to"] == 7
