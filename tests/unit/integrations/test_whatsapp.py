"""Unit tests for the WhatsApp Cloud API sender."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.whatsapp import WhatsAppConfig, send_message, send_template


@pytest.fixture()
def config():
    return WhatsAppConfig(
        token="test-token",
        phone_id="12345",
        to="9779768021317",
        enabled=True,
    )


def _ok_response():
    response = MagicMock()
    response.status_code = 200
    return response


def _client(response):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.post = AsyncMock(return_value=response)
    module = MagicMock()
    module.AsyncClient.return_value = client
    return module, client


class TestWhatsAppConfig:
    def test_ready(self, config):
        assert config.ready is True

    def test_not_ready_without_token(self, config):
        config.token = ""
        assert config.ready is False

    def test_not_ready_when_disabled(self, config):
        config.enabled = False
        assert config.ready is False


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_skips_without_config(self):
        assert await send_message("hi", config=WhatsAppConfig()) is False

    @pytest.mark.asyncio
    async def test_posts_text_payload(self, config):
        module, client = _client(_ok_response())
        with patch.dict("sys.modules", {"httpx": module}):
            assert await send_message("hello", config=config) is True
        _, kwargs = client.post.call_args
        assert kwargs["json"]["type"] == "text"
        assert kwargs["json"]["to"] == "9779768021317"
        assert "hello" in kwargs["json"]["text"]["body"]
        assert kwargs["headers"]["Authorization"] == "Bearer test-token"

    @pytest.mark.asyncio
    async def test_api_error_returns_false(self, config):
        bad = MagicMock()
        bad.status_code = 400
        bad.text = "bad request"
        module, client = _client(bad)
        with patch.dict("sys.modules", {"httpx": module}):
            assert await send_message("hi", config=config) is False

    @pytest.mark.asyncio
    async def test_template_payload(self, config):
        module, client = _client(_ok_response())
        with patch.dict("sys.modules", {"httpx": module}):
            assert await send_template(config=config) is True
        _, kwargs = client.post.call_args
        assert kwargs["json"]["type"] == "template"
        assert kwargs["json"]["template"]["name"] == "hello_world"
