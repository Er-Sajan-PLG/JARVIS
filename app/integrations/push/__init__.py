"""Push notification service for mobile PWA."""
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PushSubscription:
    """Web Push subscription."""
    endpoint: str
    keys: dict[str, str]
    user_agent: str = ""


@dataclass
class PushMessage:
    """Push notification message."""
    title: str
    body: str
    icon: str = "/static/icon.png"
    badge: str = "/static/badge.png"
    data: dict[str, Any] = field(default_factory=dict)


class PushService:
    """Web Push notification service."""
    
    def __init__(self, vapid_private_key: str = "", vapid_claims: dict | None = None):
        self.vapid_private_key = vapid_private_key
        self.vapid_claims = vapid_claims or {
            "sub": "mailto:jarvis@localhost"
        }
        self._subscriptions: list[PushSubscription] = []
    
    def add_subscription(self, subscription: PushSubscription):
        """Add a push subscription."""
        # Avoid duplicates
        existing = [s for s in self._subscriptions if s.endpoint == subscription.endpoint]
        if not existing:
            self._subscriptions.append(subscription)
            logger.info("Push subscription added: %s...", subscription.endpoint[:50])
    
    def remove_subscription(self, endpoint: str):
        """Remove a push subscription."""
        self._subscriptions = [s for s in self._subscriptions if s.endpoint != endpoint]
        logger.info("Push subscription removed: %s...", endpoint[:50])
    
    async def send(self, message: PushMessage) -> dict[str, Any]:
        """Send push notification to all subscriptions."""
        if not self.vapid_private_key:
            logger.warning("VAPID key not configured, skipping push")
            return {"success": False, "error": "VAPID key not configured"}
        
        results = {"success": 0, "failed": 0, "total": len(self._subscriptions)}
        
        for sub in self._subscriptions:
            try:
                await self._send_to_subscription(sub, message)
                results["success"] += 1
            except Exception as e:
                logger.error("Push send error: %s", e)
                results["failed"] += 1
        
        return results
    
    async def _send_to_subscription(self, subscription: PushSubscription, message: PushMessage):
        """Send push to a single subscription."""
        try:
            from pywebpush import webpush, WebPushException
            
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": subscription.keys,
                },
                data={
                    "title": message.title,
                    "body": message.body,
                    "icon": message.icon,
                    "badge": message.badge,
                    "data": message.data,
                },
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims,
            )
        except Exception as e:
            logger.error("WebPush error: %s", e)
            raise
    
    def get_subscription_count(self) -> int:
        """Get number of active subscriptions."""
        return len(self._subscriptions)
