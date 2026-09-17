"""Email sender service."""
import logging
from typing import Any

from app.integrations.email.client import EmailClient, EmailConfig

logger = logging.getLogger(__name__)


class EmailSender:
    """Service for sending emails."""

    def __init__(self, client: EmailClient | None = None):
        self.client = client or EmailClient()

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
    ) -> bool:
        """Send a new email."""
        return await self.client.send_email(
            to=to,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to,
        )

    async def reply(
        self,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str,
    ) -> bool:
        """Reply to an email."""
        return await self.client.send_email(
            to=to,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to,
        )

    async def close(self):
        """Close connections."""
        await self.client.close()
