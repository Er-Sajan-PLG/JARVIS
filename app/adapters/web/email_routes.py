"""Email REST API routes."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.http.router import validate_api_key
from app.integrations.email.client import configured_accounts
from app.integrations.email.tools import read_emails, reply_email, search_emails, send_email

logger = logging.getLogger(__name__)

email_router = APIRouter(
    prefix="/api/v1/emails", tags=["Email"], dependencies=[Depends(validate_api_key)]
)


@email_router.get("/accounts")
async def list_accounts() -> dict[str, Any]:
    """List configured mailboxes (primary is ``""``)."""
    return {"accounts": configured_accounts()}


@email_router.get("/")
async def list_emails(
    folder: str = "INBOX",
    limit: int = 50,
    unread_only: bool = False,
    account: str = "",
) -> dict[str, Any]:
    """List emails from a folder (optionally on ``account``)."""
    result = await read_emails(folder=folder, limit=limit, unread_only=unread_only, account=account)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@email_router.get("/search")
async def search_email(query: str, limit: int = 20, account: str = "") -> dict[str, Any]:
    """Search emails (optionally on ``account``)."""
    result = await search_emails(query=query, limit=limit, account=account)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@email_router.get("/{email_id}")
async def get_email(email_id: str, account: str = "") -> dict[str, Any]:
    """Get a single email by ID (optionally on ``account``)."""
    from app.integrations.email.reader import EmailReader

    reader = EmailReader(account=account)
    try:
        email = await reader.get_email(email_id.encode())
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        return email
    finally:
        await reader.close()


@email_router.post("/")
async def create_email(payload: dict[str, Any]) -> dict[str, Any]:
    """Send a new email."""
    to = payload.get("to", "")
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    account = payload.get("account", "")

    if not to or not subject:
        raise HTTPException(status_code=400, detail="to and subject required")

    result = await send_email(to=to, subject=subject, body=body, account=account)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@email_router.post("/{email_id}/reply")
async def reply_to_email(email_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Reply to an email."""
    body = payload.get("body", "")
    account = payload.get("account", "")
    if not body:
        raise HTTPException(status_code=400, detail="body required")

    result = await reply_email(email_id, body, account=account)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
