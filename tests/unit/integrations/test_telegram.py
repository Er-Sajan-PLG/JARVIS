"""Unit tests for the Telegram two-way integration."""

from unittest.mock import AsyncMock, MagicMock, patch

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


class TestSendVoice:
    @pytest.mark.asyncio
    async def test_no_token_skips(self):
        from app.integrations.telegram import send_voice

        ok = await send_voice("hi", config=TelegramConfig(token=""))
        assert ok is False

    @pytest.mark.asyncio
    async def test_empty_text_skips(self, config):
        from app.integrations.telegram import send_voice

        assert await send_voice("  ", config=config) is False

    @pytest.mark.asyncio
    async def test_voice_upload(self, config):
        import sys
        from pathlib import Path

        from app.integrations.telegram import send_voice

        async def fake_stream():
            for chunk in (b"mp3", b"data"):
                yield {"type": "audio", "data": chunk}

        edge_mod = MagicMock()
        edge_mod.Communicate.return_value.stream.return_value = fake_stream()

        completed = MagicMock()
        completed.returncode = 0

        def fake_run(cmd, **kwargs):
            Path(cmd[-1]).write_bytes(b"ogg")
            return completed

        posted = {}

        class FakeResp:
            status_code = 200
            text = "ok"

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, data=None, files=None):
                posted["url"] = url
                posted["files"] = files
                return FakeResp()

        httpx_mod = MagicMock()
        httpx_mod.AsyncClient.return_value = FakeClient()

        with (
            patch.dict(sys.modules, {"edge_tts": edge_mod}),
            patch("subprocess.run", side_effect=fake_run),
            patch.dict(sys.modules, {"httpx": httpx_mod}),
        ):
            assert await send_voice("hello there", config=config) is True

        assert posted["url"].endswith("/sendVoice")
        assert posted["files"]["voice"][0] == "brief.ogg"


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


class TestVoiceHandling:
    @pytest.mark.asyncio
    async def test_voice_message_transcribed_then_answered(self, config):
        poller = TelegramPoller(config)
        with (
            patch.object(
                poller, "_transcribe_message", new=AsyncMock(return_value="read my mail")
            ),
            patch.object(poller, "_answer", new=AsyncMock(return_value="done")) as answer,
            patch(
                "app.integrations.telegram.send_message",
                new=AsyncMock(return_value=True),
            ) as sender,
        ):
            await poller._handle_update(
                {
                    "message": {
                        "chat": {"id": 111},
                        "message_id": 9,
                        "voice": {"file_id": "abc", "duration": 3},
                    }
                }
            )
        sender.assert_called_once()
        answer.assert_called_once_with("read my mail", "111")

    @pytest.mark.asyncio
    async def test_untranscribable_voice_ignored(self, config):
        poller = TelegramPoller(config)
        with (
            patch.object(poller, "_transcribe_message", new=AsyncMock(return_value="")),
            patch.object(poller, "_answer", new=AsyncMock(return_value="x")),
            patch(
                "app.integrations.telegram.send_message",
                new=AsyncMock(return_value=True),
            ) as sender,
        ):
            await poller._handle_update(
                {"message": {"chat": {"id": 111}, "voice": {"file_id": "abc"}}}
            )
        sender.assert_not_called()
