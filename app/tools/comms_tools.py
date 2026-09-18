"""Comms tools for the ExecutionRunner: email, notifications, brief.

Reads are SAFE (no side effects). Anything that sends — email, reply,
push/Telegram notification — is SENSITIVE: rate-limited and policy-checked
like other network writes, but not HITL-gated per message (that would make
every alert wait on a human).

Handlers are async (the runner awaits coroutine tools) and return compact
JSON strings, matching how the runner surfaces step results.
"""

import json
import logging
from typing import Any

from app.domain import SafetyTier
from app.guardrails import safety_gate

logger = logging.getLogger(__name__)


def _dump(payload: dict[str, Any], max_chars: int = 4000) -> str:
    text = json.dumps(payload, default=str)
    return text if len(text) <= max_chars else text[:max_chars] + "…[truncated]"


@safety_gate(tier=SafetyTier.SAFE, description="Read emails from a folder")
async def comms_read_emails(
    folder: str = "INBOX", limit: int = 20, unread_only: bool = False
) -> str:
    """Read emails (subjects + senders + bodies, bounded)."""
    from app.integrations.email.tools import read_emails

    return _dump(await read_emails(folder=folder, limit=limit, unread_only=unread_only))


@safety_gate(tier=SafetyTier.SAFE, description="Search emails by keyword")
async def comms_search_emails(query: str, limit: int = 20) -> str:
    """Search email subjects and bodies for a keyword."""
    from app.integrations.email.tools import search_emails

    return _dump(await search_emails(query=query, limit=limit))


@safety_gate(tier=SafetyTier.SENSITIVE, description="Send an email")
async def comms_send_email(to: str, subject: str, body: str) -> str:
    """Send an email to one recipient."""
    from app.integrations.email.tools import send_email

    return _dump(await send_email(to=to, subject=subject, body=body))


@safety_gate(tier=SafetyTier.SENSITIVE, description="Reply to an email")
async def comms_reply_email(email_id: str, body: str) -> str:
    """Reply to an email by its ID."""
    from app.integrations.email.tools import reply_email

    return _dump(await reply_email(email_id=email_id, body=body))


@safety_gate(tier=SafetyTier.SENSITIVE, description="Send a phone/chat notification")
async def comms_notify(title: str, body: str, channels: str = "push") -> str:
    """Send a notification via push and/or telegram (comma-separated)."""
    from app.integrations.push import PushMessage, PushService

    wanted = [c.strip() for c in channels.split(",") if c.strip()]
    results: dict[str, Any] = {}
    if "push" in wanted:
        results["push"] = await PushService().send(PushMessage(title=title, body=body))
    if "telegram" in wanted:
        try:
            from app.integrations.telegram import send_message

            results["telegram"] = {"success": await send_message(f"{title}\n{body}")}
        except Exception as exc:  # noqa: BLE001
            results["telegram"] = {"success": False, "error": str(exc)}
    return _dump({"success": True, "results": results})


@safety_gate(tier=SafetyTier.SAFE, description="Generate the morning brief")
async def comms_brief() -> str:
    """Generate the morning brief (memory, approvals, activity)."""
    from app.integrations.brief import BriefConfig, BriefService

    service = BriefService(BriefConfig.from_env())
    return _dump(await service.generate_brief())


COMMS_TOOLS = {
    "read_emails": comms_read_emails,
    "search_emails": comms_search_emails,
    "send_email": comms_send_email,
    "reply_email": comms_reply_email,
    "send_notification": comms_notify,
    "get_brief": comms_brief,
}
