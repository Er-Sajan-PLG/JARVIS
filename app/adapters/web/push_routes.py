"""Push notification REST API routes."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.http.router import validate_api_key
from app.integrations.push import PushMessage, PushService, PushSubscription

logger = logging.getLogger(__name__)

push_router = APIRouter(
    prefix="/api/v1/push", tags=["Push"], dependencies=[Depends(validate_api_key)]
)

# Global push service instance
_push_service = PushService()

# VAPID public key is public by design (the browser needs it before any
# credential exists to create a subscription), so it lives outside the
# authed router. Gating it would make push uninstallable.
push_public_router = APIRouter(prefix="/api/v1/push", tags=["Push"])


@push_public_router.get("/vapid-public-key")
async def vapid_public_key() -> dict[str, Any]:
    """Expose the VAPID public key so browsers can subscribe."""
    import os

    key = os.environ.get("VAPID_PUBLIC_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="VAPID not configured")
    return {"publicKey": key}


@push_router.post("/subscribe")
async def subscribe(payload: dict[str, Any]) -> dict[str, Any]:
    """Register a push subscription."""
    endpoint = payload.get("endpoint", "")
    keys = payload.get("keys", {})

    if not endpoint or not keys:
        raise HTTPException(status_code=400, detail="endpoint and keys required")

    subscription = PushSubscription(
        endpoint=endpoint,
        keys=keys,
        user_agent=payload.get("user_agent", ""),
    )

    _push_service.add_subscription(subscription)

    return {
        "success": True,
        "message": "Subscribed",
        "count": _push_service.get_subscription_count(),
    }


@push_router.delete("/unsubscribe")
async def unsubscribe(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove a push subscription."""
    endpoint = payload.get("endpoint", "")
    if not endpoint:
        raise HTTPException(status_code=400, detail="endpoint required")

    _push_service.remove_subscription(endpoint)

    return {
        "success": True,
        "message": "Unsubscribed",
        "count": _push_service.get_subscription_count(),
    }


@push_router.post("/test")
async def test_push(payload: dict[str, Any]) -> dict[str, Any]:
    """Send a test push notification."""
    title = payload.get("title", "JARVIS")
    body = payload.get("body", "Test notification")

    message = PushMessage(
        title=title,
        body=body,
        data={"type": "test", "timestamp": __import__("time").time()},
    )

    result = await _push_service.send(message)
    return {"success": True, "result": result}


@push_router.get("/status")
async def push_status() -> dict[str, Any]:
    """Get push service status."""
    return {
        "subscriptions": _push_service.get_subscription_count(),
        "vapid_configured": bool(_push_service.vapid_private_key),
    }
