"""Unified notification dispatcher.

One endpoint for every "tell the operator something" path: the brain, the
brief, HITL approvals and ad-hoc alerts all POST here instead of learning
each channel. Channels resolve lazily so a missing integration (e.g. no
Telegram token) skips instead of failing the whole alert.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.http.router import validate_api_key
from app.integrations.push import PushMessage, PushService

logger = logging.getLogger(__name__)

notify_router = APIRouter(
    prefix="/api/v1/notify",
    tags=["Notify"],
    dependencies=[Depends(validate_api_key)],
)

_push_service = PushService()

VALID_CHANNELS = ("push", "telegram")


@notify_router.post("/")
async def notify(payload: dict[str, Any]) -> dict[str, Any]:
    """Send a notification via one or more channels.

    Body: {"title": str, "body": str, "channels": ["push", "telegram"],
           "data": {...}, "chat_id": "<telegram override>"}
    Defaults to push when no channels are given.
    """
    title = (payload.get("title") or "JARVIS").strip()
    body = (payload.get("body") or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="body required")

    channels = payload.get("channels") or ["push"]
    unknown = [c for c in channels if c not in VALID_CHANNELS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown channels: {unknown}")

    results: dict[str, Any] = {}
    if "push" in channels:
        message = PushMessage(title=title, body=body, data=payload.get("data") or {})
        results["push"] = await _push_service.send(message)
    if "telegram" in channels:
        results["telegram"] = await _send_telegram(title, body, payload.get("chat_id"))
    return {"success": True, "results": results}


async def _send_telegram(title: str, body: str, chat_id: str | None) -> dict[str, Any]:
    """Send via Telegram if the integration is configured, else skip."""
    try:
        from app.integrations.telegram import send_message
    except Exception as exc:  # integration absent or misconfigured
        logger.warning("Telegram channel unavailable: %s", exc)
        return {"success": False, "error": "telegram not configured"}
    try:
        text = f"*{title}*\n{body}" if title != "JARVIS" else body
        ok = await send_message(text, chat_id=chat_id)
        return {"success": ok}
    except Exception as exc:  # noqa: BLE001 - alert path must not raise
        logger.error("Telegram send error: %s", exc)
        return {"success": False, "error": str(exc)}
