# VOICE — Speech Input and Spoken Replies

**Status**: ACTIVE
**Type**: guide
**Last Updated**: 2026-09-18
**Source**: `app/adapters/web/voice_routes.py`, `frontend/assets/voice.js`, `app/integrations/telegram/__init__.py`, `tgcall/` at HEAD

> Drift trap for this type: Teaches a workflow that the reader then finds does not exist, which is worse for a beginner than no guide at all.

---

## What this is

JARVIS speaks and listens in two places that share one backend:

1. **The console** (web / PWA / APK): the mic button records, the server
   transcribes; the speaker toggle plays server-synthesised replies.
2. **Telegram**: voice notes sent to the bot are transcribed and answered
   as text.

The HTTP backend is `app/adapters/web/voice_routes.py`
(`prefix="/api/v1/voice"`, API-key gated). STT runs locally via
faster-whisper; TTS uses Edge TTS (no API key). Nothing streams —
request/response keeps the phone client simple and the server stateless.
The console client is `frontend/assets/voice.js`; the Telegram side is
`TelegramPoller` in `app/integrations/telegram/__init__.py`.

## Getting started

Every command below assumes the server is running
(`.venv/bin/python -m app.main`) and `JARVIS_API_KEY` is exported from
`.env`. First boot downloads the STT model (~75 MB), so the first
transcription is slow and later ones are fast.

```bash
KEY=$(grep '^JARVIS_API_KEY=' .env | cut -d= -f2-)

# Is the voice service up? (no model load)
curl -s -H "Authorization: Bearer $KEY" \
  http://127.0.0.1:8000/api/v1/voice/status

# Synthesise speech (MP3 bytes back)
curl -s -X POST -H "Authorization: Bearer $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Voice check successful"}' \
  http://127.0.0.1:8000/api/v1/voice/tts -o /tmp/voice-check.mp3
```

Configuration (environment, all optional):

| Variable | Meaning | Default |
|---|---|---|
| `JARVIS_STT_MODEL` | faster-whisper model: `tiny` / `base` / `small` | `tiny` |
| `JARVIS_TTS_VOICE` | Edge TTS voice id | `en-US-ChristopherNeural` |

## Common tasks

### Talk to the console (mic → STT)

1. Open the console and click the **mic button** (`#micBtn`, 🎤) in the
   composer bar: tap once, speak, tap again to send.
2. The client (`frontend/assets/voice.js`) records with `MediaRecorder`
   and POSTs the audio to `/api/v1/voice/stt`; the transcript lands in
   the composer as if typed.
3. Limits, enforced server-side: empty audio → 400, over 10 MB → 413,
   transcription failure → 500.

### Hear replies (TTS → speaker)

1. Click the **speaker toggle** (`#voiceToggle`, 🔊/🔇) in the composer
   bar to enable spoken replies for the session.
2. Each assistant reply is POSTed (as text, capped at 2000 chars) to
   `/api/v1/voice/tts`; the returned MP3 plays through a single shared
   `Audio` element, so starting a new reply stops the old one.

### Send a Telegram voice note

1. Enable the bot (`TELEGRAM_ENABLED=true`, `TELEGRAM_BOT_TOKEN`, and
   your chat in `TELEGRAM_ALLOWED_CHAT_IDS` — see `docs/COMMS.md`).
2. Record a voice message to the bot. The poller downloads it via
   `getFile`, transcribes it locally, and answers exactly as if you had
   typed the transcript.
3. The bot can also speak back: `send_voice(text, ...)` in
   `app/integrations/telegram/__init__.py` converts speech to OGG/Opus
   and uploads it as a voice bubble.

### APK microphone permission

The Android shell already declares what it needs in
`mobile/android/app/src/main/AndroidManifest.xml`:

- `RECORD_AUDIO` — the WebView mic (the `MediaRecorder` path above).
- `MODIFY_AUDIO_SETTINGS` + `INTERNET` — playback and transport.

After `npm run build-apk` (see `docs/MOBILE_ACCESS.md`), Android asks
for microphone access on first mic-button tap. If recording fails inside
an installed APK while it works in the phone browser, the cause is the
OS-level permission, not the server: check the app's permission screen,
grant Microphone, and tap the mic button again.

## Honest gaps

- **No streaming.** STT waits for the whole clip; TTS returns whole MP3
  bytes. Long replies start speaking late — by design, until a
  streaming endpoint exists.
- **`tiny` model accuracy.** The default faster-whisper model is picked
  for CPU speed, not accuracy. Set `JARVIS_STT_MODEL=base` (or `small`)
  if transcripts are poor; expect slower first-load and inference.
- **Edge TTS needs the network.** TTS calls out to the Edge service, so
  spoken replies fail offline while STT (local) keeps working.
- **No voice over `/ws/voice` from the console.** A
  `voice_ws_router` websocket exists at `/ws/voice` in
  `app/adapters/websocket/voice_handler.py`, but the console uses the
  REST endpoints above; treat the socket as experimental.

## Where to go next

- `docs/COMMS.md` — the notify dispatcher, Telegram text setup and the
  WhatsApp template rule.
- `docs/MOBILE_ACCESS.md` — install the PWA/APK, push subscribe (VAPID),
  and the Server URL setting the APK needs.
- `app/adapters/web/voice_routes.py` — endpoint source; `GET
  /api/v1/voice/status` reports the live STT/TTS configuration without
  loading a model.

## Live Telegram calls (prototype)

True person-to-person voice calls need userbot signaling + Telegram's
custom encrypted-call protocol, which no maintained library fully offers
(group-call libraries only). The scaffold lives in `tgcall/` (GramJS MTProto
signaling + VoIP DH crypto, `test-crypto.js` verified; the SRTP media bridge
to STT/TTS is the remaining blocker). Until that lands, spoken Telegram
delivery means voice notes (`send_voice`), not calls — see `docs/COMMS.md`.
