"""Telegram two-way integration: alerts out, chat in.

Send path: :func:`send_message` posts to the Bot API. Used by the notify
dispatcher and the brief.

Chat path: :class:`TelegramPoller` long-polls ``getUpdates`` and routes each
operator message through the same ``/api/chat`` pipeline the web console
uses, keyed to a per-chat session (``telegram:<chat_id>``) so the
conversation has memory. Only chats listed in ``TELEGRAM_ALLOWED_CHAT_IDS``
are answered; everyone else is ignored silently (no oracle for scanners).

The poller is a background asyncio task started from the server lifespan
when ``TELEGRAM_ENABLED=true`` and a token is present. It is deliberately
polling, not a webhook: no public HTTPS endpoint is required, which keeps
the Tailscale-only deployment model intact.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot"
_MAX_MESSAGE = 4000  # under Telegram's 4096 limit, with margin
_MIN_INTERVAL = 1.5  # seconds between replies per chat (flood guard)


@dataclass
class TelegramConfig:
    """Telegram connection configuration."""

    token: str = ""
    allowed_chat_ids: list[str] = field(default_factory=list)
    enabled: bool = False

    @classmethod
    def from_env(cls) -> "TelegramConfig":
        """Create config from environment variables."""
        token = os.getenv("TELEGRAM_BOT_TOKEN", "") or os.getenv("TELEGRAM_API_KEYS", "")
        raw_ids = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
        return cls(
            token=token.strip(),
            allowed_chat_ids=[c.strip() for c in raw_ids.split(",") if c.strip()],
            enabled=os.getenv("TELEGRAM_ENABLED", "false").lower() == "true",
        )

    @property
    def ready(self) -> bool:
        """True when the bot can operate (token + enabled)."""
        return bool(self.token) and self.enabled


async def send_message(
    text: str,
    chat_id: str | None = None,
    reply_to: int | None = None,
    config: TelegramConfig | None = None,
) -> bool:
    """Send a message via the Bot API. Returns True on success."""
    cfg = config or TelegramConfig.from_env()
    if not cfg.token:
        logger.warning("Telegram token not configured, skipping send")
        return False
    target = (chat_id or "").strip() or (cfg.allowed_chat_ids[0] if cfg.allowed_chat_ids else "")
    if not target:
        logger.warning("Telegram send has no chat_id and none allowlisted")
        return False

    import httpx

    payload: dict[str, object] = {"chat_id": target, "text": text[:_MAX_MESSAGE]}
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(f"{_API_BASE}{cfg.token}/sendMessage", json=payload)
            if res.status_code != 200:
                logger.error("Telegram send failed: %s", res.text[:200])
                return False
            return True
    except Exception as exc:  # noqa: BLE001 - network flakes must not raise
        logger.error("Telegram send error: %s", exc)
        return False


async def send_voice(
    text: str,
    chat_id: str | None = None,
    config: TelegramConfig | None = None,
) -> bool:
    """Speak text as a Telegram voice message (bot API sendVoice).

    Free, works today, no call needed: Edge TTS synthesizes MP3, ffmpeg
    converts to OGG/Opus (what voice bubbles require), then upload.
    Returns True when Telegram accepts the upload.
    """
    import subprocess
    import tempfile
    from pathlib import Path

    cfg = config or TelegramConfig.from_env()
    if not cfg.token:
        logger.warning("Telegram token not configured, skipping voice send")
        return False
    target = (chat_id or "").strip() or (cfg.allowed_chat_ids[0] if cfg.allowed_chat_ids else "")
    if not target:
        return False
    clean = (text or "").strip()[:2000]
    if not clean:
        return False

    import httpx

    try:
        import edge_tts

        communicate = edge_tts.Communicate(clean, "en-US-ChristopherNeural")
        mp3 = b"".join([c["data"] async for c in communicate.stream() if c["type"] == "audio"])
        if not mp3:
            return False
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "brief.mp3"
            dst = Path(tmp) / "brief.ogg"
            src.write_bytes(mp3)
            proc = await asyncio.to_thread(
                subprocess.run,
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(src),
                    "-c:a",
                    "libopus",
                    "-b:a",
                    "48k",
                    str(dst),
                ],
                capture_output=True,
            )
            if proc.returncode != 0 or not dst.exists():
                logger.error("ffmpeg voice convert failed")
                return False
            async with httpx.AsyncClient(timeout=60) as client:
                res = await client.post(
                    f"{_API_BASE}{cfg.token}/sendVoice",
                    data={"chat_id": target},
                    files={"voice": ("brief.ogg", dst.read_bytes(), "audio/ogg")},
                )
                if res.status_code != 200:
                    logger.error("Telegram voice failed: %s", res.text[:200])
                    return False
                return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Telegram voice error: %s", exc)
        return False


class TelegramPoller:
    """Long-poll getUpdates and answer operator messages via the chat pipeline."""

    def __init__(self, config: TelegramConfig | None = None):
        self.config = config or TelegramConfig.from_env()
        self._offset = 0
        self._running = False
        self._last_reply: dict[str, float] = {}

    async def run_forever(self) -> None:
        """Poll until cancelled. Designed to run as an asyncio Task."""
        import httpx

        self._running = True
        logger.info("Telegram poller started")
        try:
            async with httpx.AsyncClient(timeout=40) as client:
                while self._running:
                    try:
                        updates = await self._get_updates(client)
                    except Exception as exc:  # noqa: BLE001 - keep polling
                        logger.warning("Telegram poll error: %s", exc)
                        await asyncio.sleep(5)
                        continue
                    for update in updates:
                        try:
                            await self._handle_update(update)
                        except Exception as exc:  # noqa: BLE001 - one bad update
                            logger.error("Telegram update error: %s", exc)
        except asyncio.CancelledError:
            logger.info("Telegram poller stopped")
            raise
        finally:
            self._running = False

    def stop(self) -> None:
        """Signal the poll loop to exit."""
        self._running = False

    async def _get_updates(self, client) -> list[dict]:
        res = await client.get(
            f"{_API_BASE}{self.config.token}/getUpdates",
            params={"offset": self._offset, "timeout": 30},
        )
        if res.status_code != 200:
            logger.warning("getUpdates status %s", res.status_code)
            await asyncio.sleep(5)
            return []
        data = res.json()
        updates = data.get("result", [])
        for update in updates:
            self._offset = max(self._offset, update.get("update_id", 0) + 1)
        return updates

    async def _handle_update(self, update: dict) -> None:
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text = (message.get("text") or "").strip()
        if not chat_id:
            return
        if chat_id not in self.config.allowed_chat_ids:
            logger.warning("Ignoring Telegram message from unknown chat %s", chat_id)
            return

        # Voice/audio messages are transcribed first, then handled as text.
        # Without this, talking to the bot was silently ignored.
        if not text and ("voice" in message or "audio" in message):
            text = await self._transcribe_message(message) or ""
            if text:
                logger.info("Transcribed Telegram voice: %s", text[:80])
        if not text:
            return

        # Flood guard: at most one reply per interval per chat.
        now = asyncio.get_running_loop().time()
        if now - self._last_reply.get(chat_id, 0) < _MIN_INTERVAL:
            return
        self._last_reply[chat_id] = now

        reply = await self._answer(text, chat_id)
        chunks = [reply[i : i + _MAX_MESSAGE] for i in range(0, len(reply), _MAX_MESSAGE)]
        for chunk in chunks or ["…"]:
            await send_message(
                chunk,
                chat_id=chat_id,
                reply_to=message.get("message_id"),
                config=self.config,
            )

    async def _transcribe_message(self, message: dict) -> str:
        """Download a voice/audio attachment and transcribe it locally."""
        import tempfile
        from pathlib import Path

        file_id = ((message.get("voice") or message.get("audio")) or {}).get("file_id")
        if not file_id:
            return ""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=60) as client:
                info = await client.get(
                    f"{_API_BASE}{self.config.token}/getFile",
                    params={"file_id": file_id},
                )
                if info.status_code != 200:
                    return ""
                file_path = info.json().get("result", {}).get("file_path", "")
                if not file_path:
                    return ""
                dl = await client.get(
                    f"https://api.telegram.org/file/bot{self.config.token}/{file_path}"
                )
                if dl.status_code != 200 or not dl.content:
                    return ""
                from faster_whisper import WhisperModel

                model = WhisperModel("tiny", device="cpu", compute_type="int8")
                suffix = Path(file_path).suffix or ".ogg"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
                    tmp.write(dl.content)
                    tmp.flush()
                    segments, _ = model.transcribe(tmp.name)
                    return " ".join(s.text for s in segments).strip()
        except Exception as exc:  # noqa: BLE001
            logger.error("Telegram voice transcribe error: %s", exc)
            return ""

    async def _answer(self, text: str, chat_id: str) -> str:
        """Route one message through the web chat pipeline."""
        from app.adapters.web.router import chat as web_chat

        try:
            result = await web_chat(
                {
                    "message": text,
                    "session_id": f"telegram:{chat_id}",
                    "memory_enabled": True,
                }
            )
        except Exception as exc:  # noqa: BLE001 - always answer something
            logger.error("Telegram chat pipeline error: %s", exc)
            return "Something went wrong on my end. Try again."
        if isinstance(result, dict):
            for key in ("reply", "response", "content", "message"):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return "Done."
