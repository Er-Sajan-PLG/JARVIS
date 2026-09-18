"""Push notification service for mobile PWA.

Subscriptions are persisted to ``data/push_subscriptions.json`` so they survive
server restarts. Without persistence, every reboot would silently drop every
phone's registration and push notifications would stop working until the user
re-opened the app.

The VAPID keys are read from the environment (populated by ``.env``). The
public key is exposed via ``/api/v1/push/vapid-public-key`` so the browser can
subscribe without hardcoding anything.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SUBSCRIPTIONS_FILE = _PROJECT_ROOT / "data" / "push_subscriptions.json"


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
    icon: str = "/icon-192.png"
    badge: str = "/badge.png"
    data: dict[str, Any] = field(default_factory=dict)


class PushService:
    """Web Push notification service with persistent subscription storage."""

    def __init__(
        self,
        vapid_private_key: str = "",
        vapid_claims: dict | None = None,
        storage_path: Path | None = None,
    ):
        self.vapid_private_key = vapid_private_key or os.environ.get("VAPID_PRIVATE_KEY", "")
        claims_email = os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:jarvis@localhost")
        self.vapid_claims = vapid_claims or {"sub": claims_email}
        self._storage_path = storage_path or _SUBSCRIPTIONS_FILE
        self._subscriptions: list[PushSubscription] = []
        self._load()

    # -- Persistence ----------------------------------------------------------

    def _load(self) -> None:
        """Load subscriptions from disk."""
        if not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
            self._subscriptions = [PushSubscription(**entry) for entry in raw]
            logger.info(
                "Loaded %d push subscription(s) from disk",
                len(self._subscriptions),
            )
        except Exception:
            logger.exception("Failed to load push subscriptions")
            self._subscriptions = []

    def _save(self) -> None:
        """Persist current subscriptions to disk."""
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = [asdict(sub) for sub in self._subscriptions]
            self._storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("Failed to save push subscriptions")

    # -- Subscription management ----------------------------------------------

    def add_subscription(self, subscription: PushSubscription) -> None:
        """Add a push subscription and persist it."""
        existing = [s for s in self._subscriptions if s.endpoint == subscription.endpoint]
        if existing:
            existing[0].keys = subscription.keys
            existing[0].user_agent = subscription.user_agent
        else:
            self._subscriptions.append(subscription)
            logger.info("Push subscription added: %s...", subscription.endpoint[:60])
        self._save()

    def remove_subscription(self, endpoint: str) -> None:
        """Remove a push subscription and persist the change."""
        before = len(self._subscriptions)
        self._subscriptions = [s for s in self._subscriptions if s.endpoint != endpoint]
        if len(self._subscriptions) < before:
            logger.info("Push subscription removed: %s...", endpoint[:60])
            self._save()

    def get_subscription_count(self) -> int:
        """Get number of active subscriptions."""
        return len(self._subscriptions)

    # -- Sending --------------------------------------------------------------

    async def send(self, message: PushMessage) -> dict[str, Any]:
        """Send push notification to all subscriptions."""
        if not self.vapid_private_key:
            logger.warning("VAPID key not configured, skipping push")
            return {"success": False, "error": "VAPID key not configured"}

        results: dict[str, Any] = {
            "success": 0,
            "failed": 0,
            "total": len(self._subscriptions),
        }
        stale_endpoints: list[str] = []

        for sub in self._subscriptions:
            try:
                await self._send_to_subscription(sub, message)
                results["success"] += 1
            except Exception as e:
                error_str = str(e)
                if "410" in error_str or "expired" in error_str.lower():
                    stale_endpoints.append(sub.endpoint)
                logger.error("Push send error: %s", e)
                results["failed"] += 1

        for ep in stale_endpoints:
            self.remove_subscription(ep)

        return results

    async def _send_to_subscription(
        self, subscription: PushSubscription, message: PushMessage
    ) -> None:
        """Send push to a single subscription."""
        from pywebpush import WebPushException, webpush

        payload = json.dumps(
            {
                "title": message.title,
                "body": message.body,
                "icon": message.icon,
                "badge": message.badge,
                "data": message.data,
            }
        )

        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": subscription.keys,
                },
                data=payload,
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims,
            )
        except WebPushException as e:
            logger.error("WebPush error for %s: %s", subscription.endpoint[:60], e)
            raise
