"""Email tools for agent."""
import logging
from typing import Any

from app.integrations.email.reader import EmailReader
from app.integrations.email.sender import EmailSender

logger = logging.getLogger(__name__)


async def read_emails(
    folder: str = "INBOX",
    limit: int = 20,
    unread_only: bool = False,
) -> dict[str, Any]:
    """Read emails from a folder."""
    reader = EmailReader()
    try:
        if unread_only:
            emails = await reader.get_unread(limit=limit)
        else:
            emails = await reader.get_all(folder=folder, limit=limit)
        return {"success": True, "emails": emails, "count": len(emails)}
    except Exception as e:
        logger.error("read_emails error: %s", e)
        return {"success": False, "error": str(e)}
    finally:
        await reader.close()


async def send_email(
    to: str,
    subject: str,
    body: str,
    in_reply_to: str | None = None,
) -> dict[str, Any]:
    """Send an email."""
    sender = EmailSender()
    try:
        result = await sender.send(
            to=to,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to,
        )
        return {"success": result, "message": "Email sent" if result else "Failed to send"}
    except Exception as e:
        logger.error("send_email error: %s", e)
        return {"success": False, "error": str(e)}
    finally:
        await sender.close()


async def reply_email(email_id: str, body: str) -> dict[str, Any]:
    """Reply to an email."""
    reader = EmailReader()
    sender = EmailSender()
    try:
        email = await reader.get_email(email_id.encode())
        if not email:
            return {"success": False, "error": "Email not found"}

        result = await sender.reply(
            to=email["from"],
            subject=f"Re: {email['subject']}",
            body=body,
            in_reply_to=email.get("message_id", ""),
        )
        return {"success": result, "message": "Reply sent" if result else "Failed to send"}
    except Exception as e:
        logger.error("reply_email error: %s", e)
        return {"success": False, "error": str(e)}
    finally:
        await reader.close()
        await sender.close()


async def search_emails(query: str, limit: int = 20) -> dict[str, Any]:
    """Search emails by query."""
    reader = EmailReader()
    try:
        emails = await reader.search(query, limit=limit)
        return {"success": True, "emails": emails, "count": len(emails)}
    except Exception as e:
        logger.error("search_emails error: %s", e)
        return {"success": False, "error": str(e)}
    finally:
        await reader.close()
