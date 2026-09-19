"""Unit tests for email client."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_aioimaplib():
    """Mock aioimaplib module."""
    mock_module = MagicMock()
    mock_instance = AsyncMock()
    mock_module.IMAP4_SSL.return_value = mock_instance
    return mock_module, mock_instance


@pytest.fixture
def mock_aiosmtplib():
    """Mock aiosmtplib module."""
    mock_module = MagicMock()
    mock_instance = AsyncMock()
    mock_module.SMTP.return_value = mock_instance
    return mock_module, mock_instance


@pytest.fixture
def config():
    from app.integrations.email.client import EmailConfig

    return EmailConfig(
        imap_host="imap.test.com",
        imap_port=993,
        smtp_host="smtp.test.com",
        smtp_port=587,
        address="test@example.com",
        password="testpass",
    )


@pytest.fixture
def client(config):
    from app.integrations.email.client import EmailClient

    return EmailClient(config)


@pytest.mark.asyncio
async def test_connect_imap(client, mock_aioimaplib):
    """Test IMAP connection."""
    mock_module, mock_instance = mock_aioimaplib
    mock_instance.wait_hello_from_server = AsyncMock()
    mock_instance.login = AsyncMock(return_value=("OK", [b"Logged in"]))
    mock_instance.select = AsyncMock(return_value=("OK", [b"1"]))

    with patch.dict(sys.modules, {"aioimaplib": mock_module}):
        result = await client._connect_imap()

    assert result is True
    mock_instance.wait_hello_from_server.assert_called_once()
    mock_instance.login.assert_called_once_with("test@example.com", "testpass")
    mock_instance.select.assert_called_once_with("INBOX")


@pytest.mark.asyncio
async def test_connect_imap_failure(client, mock_aioimaplib):
    """Test IMAP connection failure."""
    mock_module, mock_instance = mock_aioimaplib
    mock_instance.wait_hello_from_server = AsyncMock(
        side_effect=ConnectionError("Connection refused")
    )

    with patch.dict(sys.modules, {"aioimaplib": mock_module}):
        result = await client._connect_imap()

    assert result is False


@pytest.mark.asyncio
async def test_search_emails(client, mock_aioimaplib):
    """Test searching emails."""
    mock_module, mock_instance = mock_aioimaplib
    mock_instance.wait_hello_from_server = AsyncMock()
    mock_instance.login = AsyncMock(return_value=("OK", [b"Logged in"]))
    mock_instance.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_instance.search = AsyncMock(return_value=("OK", [b"1 2 3"]))

    with patch.dict(sys.modules, {"aioimaplib": mock_module}):
        result = await client.search_emails(unread_only=True)

    assert result == ["1", "2", "3"]
    mock_instance.search.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_email(client, mock_aioimaplib):
    """Test fetching a single email."""
    mock_module, mock_instance = mock_aioimaplib
    mock_instance.wait_hello_from_server = AsyncMock()
    mock_instance.login = AsyncMock(return_value=("OK", [b"Logged in"]))
    mock_instance.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_instance.fetch = AsyncMock(
        return_value=("OK", [b"1 (RFC822 {1000}", b"Email body...", b")"])
    )

    with patch.dict(sys.modules, {"aioimaplib": mock_module}):
        result = await client.fetch_email(b"1")

    assert result is not None
    assert result["id"] == b"1"
    assert "body" in result


@pytest.mark.asyncio
async def test_send_email(client, mock_aiosmtplib):
    """Test sending email via SMTP."""
    mock_module, mock_instance = mock_aiosmtplib
    mock_instance.connect = AsyncMock()
    mock_instance.login = AsyncMock()
    mock_instance.send_message = AsyncMock()
    mock_instance.quit = AsyncMock()

    with patch.dict(sys.modules, {"aiosmtplib": mock_module}):
        result = await client.send_email(
            to="recipient@example.com",
            subject="Test Subject",
            body="Test Body",
        )

    assert result is True
    mock_instance.connect.assert_called_once()
    mock_instance.login.assert_called_once_with("test@example.com", "testpass")
    mock_instance.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_failure(client, mock_aiosmtplib):
    """Test sending email failure."""
    mock_module, mock_instance = mock_aiosmtplib
    mock_instance.connect = AsyncMock(side_effect=ConnectionError("SMTP down"))

    with patch.dict(sys.modules, {"aiosmtplib": mock_module}):
        result = await client.send_email(
            to="recipient@example.com",
            subject="Test",
            body="Body",
        )

    assert result is False


@pytest.mark.asyncio
async def test_mark_as_read(client, mock_aioimaplib):
    """Test marking email as read."""
    mock_module, mock_instance = mock_aioimaplib
    mock_instance.wait_hello_from_server = AsyncMock()
    mock_instance.login = AsyncMock(return_value=("OK", [b"Logged in"]))
    mock_instance.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_instance.store = AsyncMock(return_value=("OK", [b"1"]))

    with patch.dict(sys.modules, {"aioimaplib": mock_module}):
        result = await client.mark_as_read(b"1")

    assert result is True
    mock_instance.store.assert_called_once()


@pytest.mark.asyncio
async def test_smtp_587_uses_starttls_not_implicit_tls(client, mock_aiosmtplib):
    """Port 587 is STARTTLS: implicit TLS breaks with WRONG_VERSION_NUMBER."""
    mock_module, mock_instance = mock_aiosmtplib
    mock_instance.connect = AsyncMock()
    mock_instance.login = AsyncMock()

    with patch.dict(sys.modules, {"aiosmtplib": mock_module}):
        result = await client._connect_smtp()

    assert result is True
    _, kwargs = mock_module.SMTP.call_args
    assert kwargs["port"] == 587
    assert kwargs["use_tls"] is False
    assert kwargs["start_tls"] is True
    # The library negotiates STARTTLS on connect; no explicit call.
    mock_instance.starttls.assert_not_called()
    mock_instance.login.assert_called_once()


@pytest.mark.asyncio
async def test_smtp_465_uses_implicit_tls(mock_aiosmtplib):
    """Port 465 is implicit TLS: no STARTTLS negotiation."""
    from app.integrations.email.client import EmailClient, EmailConfig

    mock_module, mock_instance = mock_aiosmtplib
    mock_instance.connect = AsyncMock()
    mock_instance.login = AsyncMock()

    client = EmailClient(
        EmailConfig(
            smtp_host="smtp.test.com",
            smtp_port=465,
            address="test@example.com",
            password="testpass",
        )
    )
    with patch.dict(sys.modules, {"aiosmtplib": mock_module}):
        result = await client._connect_smtp()

    assert result is True
    _, kwargs = mock_module.SMTP.call_args
    assert kwargs["use_tls"] is True
    assert kwargs["start_tls"] is False


def test_app_password_spaces_stripped():
    """Gmail displays app passwords grouped; the wire format has no spaces."""
    from app.integrations.email.client import EmailConfig

    cfg = EmailConfig(address="a@b.c", password="abcd efgh ijkl mnop")
    assert cfg.password == "abcdefghijklmnop"


class TestMultiAccount:
    def test_configured_accounts_primary_only(self, monkeypatch):
        from app.integrations.email.client import configured_accounts

        monkeypatch.delenv("JARVIS_EMAIL_ADDRESS", raising=False)
        monkeypatch.delenv("JARVIS_EMAIL_PASSWORD", raising=False)
        monkeypatch.setenv("JARVIS_EMAIL_ADDRESS", "a@b.c")
        monkeypatch.setenv("JARVIS_EMAIL_PASSWORD", "x")
        assert configured_accounts() == [""]

    def test_configured_accounts_discovers_second(self, monkeypatch):
        from app.integrations.email.client import configured_accounts

        monkeypatch.delenv("JARVIS_EMAIL_ADDRESS", raising=False)
        monkeypatch.delenv("JARVIS_EMAIL_PASSWORD", raising=False)
        monkeypatch.setenv("JARVIS_EMAIL_ADDRESS", "a@b.c")
        monkeypatch.setenv("JARVIS_EMAIL_PASSWORD", "x")
        monkeypatch.setenv("JARVIS_EMAIL_2_ADDRESS", "two@b.c")
        monkeypatch.setenv("JARVIS_EMAIL_2_PASSWORD", "y")
        assert configured_accounts() == ["", "2"]

    def test_configured_accounts_skips_incomplete(self, monkeypatch):
        from app.integrations.email.client import configured_accounts

        monkeypatch.delenv("JARVIS_EMAIL_ADDRESS", raising=False)
        monkeypatch.delenv("JARVIS_EMAIL_PASSWORD", raising=False)
        monkeypatch.setenv("JARVIS_EMAIL_ADDRESS", "a@b.c")
        monkeypatch.setenv("JARVIS_EMAIL_PASSWORD", "x")
        monkeypatch.setenv("JARVIS_EMAIL_2_ADDRESS", "two@b.c")  # no password
        assert configured_accounts() == [""]

    def test_from_account_reads_numbered(self, monkeypatch):
        from app.integrations.email.client import EmailConfig

        monkeypatch.setenv("JARVIS_EMAIL_2_ADDRESS", "two@b.c")
        monkeypatch.setenv("JARVIS_EMAIL_2_PASSWORD", "abcd efgh")
        cfg = EmailConfig.from_account("2")
        assert cfg.address == "two@b.c"
        assert cfg.password == "abcdefgh"  # spaces stripped

    def test_from_account_falls_back_to_global_host(self, monkeypatch):
        from app.integrations.email.client import EmailConfig

        monkeypatch.setenv("JARVIS_EMAIL_2_ADDRESS", "two@b.c")
        monkeypatch.setenv("JARVIS_EMAIL_2_PASSWORD", "p")
        cfg = EmailConfig.from_account("2")
        assert cfg.imap_host == "imap.gmail.com"  # no per-account override


class TestToolsAccountThreading:
    @pytest.mark.asyncio
    async def test_read_emails_forwards_account(self):
        from app.integrations.email.tools import read_emails

        with patch(
            "app.integrations.email.tools.EmailReader"
        ) as reader_cls:
            reader_cls.return_value.get_unread = AsyncMock(return_value=[])
            reader_cls.return_value.close = AsyncMock()
            await read_emails(unread_only=True, account="2")
        kwargs = reader_cls.call_args.kwargs
        assert kwargs.get("account") == "2"
