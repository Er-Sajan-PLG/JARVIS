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
    account: str = "",
) -> dict[str, Any]:
    """Read emails from a folder. ``account`` selects a configured mailbox."""
    reader = EmailReader(account=account)
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
    account: str = "",
) -> dict[str, Any]:
    """Send an email. ``account`` selects the sending mailbox."""
    sender = EmailSender(account=account)
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


async def reply_email(email_id: str, body: str, account: str = "") -> dict[str, Any]:
    """Reply to an email. ``account`` selects the mailbox."""
    reader = EmailReader(account=account)
    sender = EmailSender(account=account)
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


async def search_emails(query: str, limit: int = 20, account: str = "") -> dict[str, Any]:
    """Search emails by query. ``account`` selects the mailbox."""
    reader = EmailReader(account=account)
    try:
        emails = await reader.search(query, limit=limit)
        return {"success": True, "emails": emails, "count": len(emails)}
    except Exception as e:
        logger.error("search_emails error: %s", e)
        return {"success": False, "error": str(e)}
    finally:
        await reader.close()


async def summarize_unread(limit: int = 30, max_chars: int = 2000, account: str = "") -> str:
    """Compact unread digest for chat context injection.

    Returns sender frequencies plus recent subjects, bounded so it cannot
    blow up the prompt. Empty string when there is nothing to report —
    the caller then injects no context at all.
    """
    from collections import Counter

    reader = EmailReader(account=account)
    try:
        emails = await reader.get_unread(limit=limit)
    except Exception as e:
        logger.error("summarize_unread error: %s", e)
        return ""
    finally:
        await reader.close()

    if not emails:
        return "No unread emails."

    senders = Counter((e.get("from") or "?") for e in emails)
    top = ", ".join(f"{s} ({c})" for s, c in senders.most_common(5))
    lines = [f"UNREAD: {len(emails)} (showing up to {limit}).", f"Top senders: {top}."]
    for e in emails[:10]:
        subj = (e.get("subject") or "(no subject)")[:80]
        frm = (e.get("from") or "?")[:50]
        lines.append(f"- {frm}: {subj}")
    digest = "\n".join(lines)
    return digest[:max_chars]
