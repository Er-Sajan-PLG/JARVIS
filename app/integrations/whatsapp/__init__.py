"""WhatsApp Business Platform (Cloud API) sender.

One direction only: JARVIS → operator. Sending is plain outbound HTTPS, so
it works behind NAT with no public endpoint. Receiving (webhooks) is NOT
implemented: Meta requires a public HTTPS callback URL, which a
Tailscale-only deployment does not have.

Setup (Meta developer dashboard):
  1. Create an app with the WhatsApp product. Meta issues a test number
     immediately — use it before touching the real one.
  2. To send from YOUR number (9768021317): migrate it. Migrating means
     deleting it from the WhatsApp Business APP first (app chats do not
     carry over). This is the point of no return — try the test number first.
  3. Create a permanent System User access token (never the 24h test token
     for anything that must keep working).
  4. First contact must use an approved template (Meta rule for
     business-initiated messages). After the operator replies, a 24h
     customer-service window opens for free-form text.

Env:
  WHATSAPP_TOKEN        permanent access token
  WHATSAPP_PHONE_ID     sending Phone Number ID (from the dashboard)
  WHATSAPP_TO           operator's chat number, e.g. 9779768021317
  WHATSAPP_TEMPLATE     hello_world-style template name (default below)
  WHATSAPP_ENABLED      true to let the notify dispatcher use it
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_API_BASE = "https://graph.facebook.com/v21.0"


@dataclass
class WhatsAppConfig:
    """WhatsApp Cloud API configuration."""

    token: str = ""
    phone_id: str = ""
    to: str = ""
    template: str = "hello_world"
    enabled: bool = False

    @classmethod
    def from_env(cls) -> "WhatsAppConfig":
        """Create config from environment variables."""
        return cls(
            token=os.getenv("WHATSAPP_TOKEN", "").strip(),
            phone_id=os.getenv("WHATSAPP_PHONE_ID", "").strip(),
            to=os.getenv("WHATSAPP_TO", "").strip(),
            template=os.getenv("WHATSAPP_TEMPLATE", "hello_world").strip(),
            enabled=os.getenv("WHATSAPP_ENABLED", "false").lower() == "true",
        )

    @property
    def ready(self) -> bool:
        """True when a send is possible."""
        return bool(self.token and self.phone_id and self.to) and self.enabled


async def send_message(
    text: str,
    to: str | None = None,
    config: WhatsAppConfig | None = None,
) -> bool:
    """Send a free-form text message (needs an open 24h window).

    Returns True when Meta accepts the message for delivery.
    """
    cfg = config or WhatsAppConfig.from_env()
    if not cfg.token or not cfg.phone_id:
        logger.warning("WhatsApp not configured, skipping send")
        return False
    target = (to or "").strip() or cfg.to
    if not target:
        logger.warning("WhatsApp send has no recipient")
        return False

    import httpx

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post(
                f"{_API_BASE}/{cfg.phone_id}/messages",
                headers={"Authorization": f"Bearer {cfg.token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": target,
                    "type": "text",
                    "text": {"body": text[:4000]},
                },
            )
            if res.status_code not in (200, 201):
                logger.error("WhatsApp send failed: %s", res.text[:200])
                return False
            return True
    except Exception as exc:  # noqa: BLE001 - network flakes must not raise
        logger.error("WhatsApp send error: %s", exc)
        return False


async def send_template(
    to: str | None = None,
    config: WhatsAppConfig | None = None,
) -> bool:
    """Send the configured template (for first contact, no window needed)."""
    cfg = config or WhatsAppConfig.from_env()
    if not cfg.token or not cfg.phone_id:
        logger.warning("WhatsApp not configured, skipping send")
        return False
    target = (to or "").strip() or cfg.to
    if not target:
        return False

    import httpx

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post(
                f"{_API_BASE}/{cfg.phone_id}/messages",
                headers={"Authorization": f"Bearer {cfg.token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": target,
                    "type": "template",
                    "template": {"name": cfg.template, "language": {"code": "en_US"}},
                },
            )
            if res.status_code not in (200, 201):
                logger.error("WhatsApp template failed: %s", res.text[:200])
                return False
            return True
    except Exception as exc:  # noqa: BLE001
        logger.error("WhatsApp template error: %s", exc)
        return False
