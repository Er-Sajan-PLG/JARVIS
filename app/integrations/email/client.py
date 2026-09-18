"""IMAP/SMTP email client wrapper."""

import contextlib
import logging
from dataclasses import dataclass
from email import message_from_bytes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    """Email connection configuration."""

    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    address: str = ""
    password: str = ""
    use_ssl: bool = True

    def __post_init__(self) -> None:
        # Gmail shows app passwords as "abcd efgh ijkl mnop" — the spaces are
        # display grouping and must not go on the wire (SMTP AUTH rejects them
        # even where IMAP tolerates them).
        self.password = self.password.replace(" ", "")

    @classmethod
    def from_env(cls) -> "EmailConfig":
        """Create config from environment variables."""
        import os

        return cls(
            imap_host=os.getenv("JARVIS_EMAIL_IMAP_HOST", "imap.gmail.com"),
            imap_port=int(os.getenv("JARVIS_EMAIL_IMAP_PORT", "993")),
            smtp_host=os.getenv("JARVIS_EMAIL_SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("JARVIS_EMAIL_SMTP_PORT", "587")),
            address=os.getenv("JARVIS_EMAIL_ADDRESS", ""),
            password=os.getenv("JARVIS_EMAIL_PASSWORD", ""),
        )


class EmailClient:
    """Async IMAP/SMTP email client."""

    def __init__(self, config: EmailConfig | None = None):
        self.config = config or EmailConfig.from_env()
        self._imap = None
        self._smtp = None

    async def _connect_imap(self) -> bool:
        """Establish IMAP connection."""
        try:
            from aioimaplib import IMAP4_SSL

            self._imap = IMAP4_SSL(host=self.config.imap_host, port=self.config.imap_port)
            await self._imap.wait_hello_from_server()
            response = await self._imap.login(self.config.address, self.config.password)
            if response[0] != "OK":
                logger.error("IMAP login failed: %s", response)
                return False
            await self._imap.select("INBOX")
            return True
        except Exception as e:
            logger.error("IMAP connection error: %s", e)
            return False

    async def _connect_smtp(self) -> bool:
        """Establish SMTP connection.

        Port 587 expects STARTTLS (plain connect, then upgrade); port 465
        expects implicit TLS. Mixing them up yields
        ``SSL: WRONG_VERSION_NUMBER`` against Gmail.
        """
        try:
            from aiosmtplib import SMTP

            implicit_tls = self.config.use_ssl and self.config.smtp_port == 465
            self._smtp = SMTP(
                hostname=self.config.smtp_host,
                port=self.config.smtp_port,
                use_tls=implicit_tls,
                # aiosmtplib negotiates STARTTLS itself on connect; calling
                # starttls() explicitly afterwards raises "already using TLS".
                start_tls=not implicit_tls,
            )
            await self._smtp.connect()
            await self._smtp.login(self.config.address, self.config.password)
            return True
        except Exception as e:
            logger.error("SMTP connection error: %s", e)
            return False

    async def search_emails(
        self,
        folder: str = "INBOX",
        criteria: str = "ALL",
        limit: int = 50,
        unread_only: bool = False,
    ) -> list[bytes]:
        """Search emails and return message IDs."""
        if not self._imap:
            connected = await self._connect_imap()
            if not connected:
                return []

        try:
            response = None
            if self._imap:
                await self._imap.select(folder)
                search_criteria = "UNSEEN" if unread_only else criteria
                response = await self._imap.search(search_criteria)
            if response is None or response[0] != "OK":
                return []

            ids = response[1][0].decode().split()
            return ids[-limit:] if len(ids) > limit else ids
        except Exception as e:
            logger.error("Email search error: %s", e)
            return []

    async def fetch_email(self, msg_id: bytes) -> dict[str, Any] | None:
        """Fetch a single email by ID."""
        if not self._imap:
            connected = await self._connect_imap()
            if not connected:
                return None

        try:
            response = await self._imap.fetch(msg_id, "RFC822")
            if response[0] != "OK":
                return None

            raw = response[1][1]
            msg = message_from_bytes(raw)

            return {
                "id": msg_id,
                "from": msg["From"],
                "to": msg["To"],
                "subject": msg["Subject"],
                "date": msg["Date"],
                "body": self._get_body(msg),
                "attachments": len(msg.get_payload()) > 1 if msg.is_multipart() else 0,
            }
        except Exception as e:
            logger.error("Email fetch error: %s", e)
            return None

    def _get_body(self, msg) -> str:
        """Extract text body from email message."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode("utf-8", errors="replace")
        return msg.get_payload(decode=True).decode("utf-8", errors="replace")

    async def mark_as_read(self, msg_id: bytes) -> bool:
        """Mark an email as read."""
        if not self._imap:
            connected = await self._connect_imap()
            if not connected:
                return False

        try:
            response = await self._imap.store(msg_id, "+FLAGS", r"\Seen")
            return response[0] == "OK"
        except Exception as e:
            logger.error("Mark as read error: %s", e)
            return False

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
    ) -> bool:
        """Send an email."""
        if not self._smtp:
            connected = await self._connect_smtp()
            if not connected:
                return False

        try:
            msg = MIMEMultipart()
            msg["From"] = self.config.address
            msg["To"] = to
            msg["Subject"] = subject
            if in_reply_to:
                msg["In-Reply-To"] = in_reply_to
                msg["References"] = in_reply_to

            msg.attach(MIMEText(body, "plain"))

            await self._smtp.send_message(msg)
            logger.info("Email sent to %s: %s", to, subject)
            return True
        except Exception as e:
            logger.error("Send email error: %s", e)
            return False

    async def close(self):
        """Close all connections."""
        if self._imap:
            with contextlib.suppress(Exception):
                await self._imap.logout()
        if self._smtp:
            with contextlib.suppress(Exception):
                await self._smtp.quit()
