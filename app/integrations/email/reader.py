"""Email reader service."""

import logging
from typing import Any

from app.integrations.email.client import EmailClient, EmailConfig

logger = logging.getLogger(__name__)


class EmailReader:
    """Service for reading and parsing emails."""

    def __init__(self, client: EmailClient | None = None, account: str = ""):
        self.client = client or EmailClient(EmailConfig.from_account(account))
        self.account = account

    async def get_unread(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get unread emails."""
        ids = await self.client.search_emails(criteria="UNSEEN", limit=limit)
        emails = []
        for msg_id in ids:
            email = await self.client.fetch_email(msg_id)
            if email:
                emails.append(email)
        return emails

    async def get_all(self, folder: str = "INBOX", limit: int = 50) -> list[dict[str, Any]]:
        """Get all emails from a folder."""
        ids = await self.client.search_emails(folder=folder, criteria="ALL", limit=limit)
        emails = []
        for msg_id in ids:
            email = await self.client.fetch_email(msg_id)
            if email:
                emails.append(email)
        return emails

    async def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search emails by subject or body content."""
        ids = await self.client.search_emails(criteria="ALL", limit=100)
        results = []
        for msg_id in ids:
            email = await self.client.fetch_email(msg_id)
            if email and (
                query.lower() in email.get("subject", "").lower()
                or query.lower() in email.get("body", "").lower()
            ):
                results.append(email)
            if len(results) >= limit:
                break
        return results

    async def get_email(self, msg_id: bytes) -> dict[str, Any] | None:
        """Get a single email by ID."""
        return await self.client.fetch_email(msg_id)

    async def mark_read(self, msg_id: bytes) -> bool:
        """Mark an email as read."""
        return await self.client.mark_as_read(msg_id)

    async def close(self):
        """Close connections."""
        await self.client.close()
