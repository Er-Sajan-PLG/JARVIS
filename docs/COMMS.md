# COMMS — Notification, Messaging and Brief Channels

**Status**: ACTIVE
**Type**: reference
**Last Updated**: 2026-09-18
**Source**: `app/adapters/web/notify_routes.py`, `app/adapters/web/brief_routes.py`, `app/adapters/web/email_routes.py`, `app/adapters/web/push_routes.py` at HEAD

> Drift trap for this type: The fastest-rotting type. Every default, field and endpoint is duplicated from code, so every code change makes it stale.

---

## Overview

All outbound communication goes through small FastAPI routers in
`app/adapters/web/`, backed by integrations in `app/integrations/`. The
pattern is uniform: one router per surface, every route gated by
`validate_api_key` (from `app/adapters/http/router.py`), thin handlers that
delegate to an integration module which reads its own `*_ENABLED` /
token variables from the environment.

| Surface | Router | Integration | Direction |
|---|---|---|---|
| Unified notify dispatcher | `app/adapters/web/notify_routes.py` | `app/integrations/push/__init__.py`, `app/integrations/telegram/__init__.py`, `app/integrations/whatsapp/__init__.py` | out |
| Push (Web Push / VAPID) | `app/adapters/web/push_routes.py` | `app/integrations/push/__init__.py` | out |
| Telegram bot | (via notify + poller) | `app/integrations/telegram/__init__.py` | two-way |
| WhatsApp Cloud API | (via notify) | `app/integrations/whatsapp/__init__.py` | out only |
| Email (IMAP/SMTP) | `app/adapters/web/email_routes.py` | `app/integrations/email/client.py` | two-way |
| Morning brief | `app/adapters/web/brief_routes.py` | `app/integrations/brief/__init__.py` | out |

## Source of Truth

The routers are the contract; the integrations hold the defaults. When this
document and the code disagree, the code wins:

- Channel list and dispatch: `_send_telegram` / `_send_whatsapp` in
  `app/adapters/web/notify_routes.py`
- Push subscribe/VAPID: `app/adapters/web/push_routes.py`
- Brief generate/deliver: `generate_brief` / `deliver` in
  `app/integrations/brief/__init__.py`
- Telegram two-way + voice notes: `TelegramPoller`, `send_message`,
  `send_voice` in `app/integrations/telegram/__init__.py`
- WhatsApp send-only + template rule: `send_message` / `send_template` in
  `app/integrations/whatsapp/__init__.py`
- Voice input/output over HTTP: `docs/VOICE.md`,
  `app/adapters/web/voice_routes.py`

## Configuration / Interface

### Notify dispatcher — `POST /api/v1/notify/`

One endpoint for every "tell the operator something" path: the brain, the
brief, HITL approvals and ad-hoc alerts all POST here instead of learning
each channel. Channels resolve lazily, so a missing integration skips
instead of failing the whole alert.

```bash
KEY=$(grep '^JARVIS_API_KEY=' .env | cut -d= -f2-)
curl -s -X POST http://127.0.0.1:8000/api/v1/notify/ \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"title":"JARVIS","body":"Gate finished green","channels":["push","telegram"]}'
```

Body fields: `title` (default `"JARVIS"`), `body` (required),
`channels` (any of `push`, `telegram`, `whatsapp`; defaults to
`["push"]`), `data` (push payload), `chat_id` (Telegram override).
Unknown channel names return HTTP 400. Each channel result is reported
per-channel (`{"success": True, "results": {...}}`), so one down channel
never masks the others.

### Telegram — two-way + voice notes

`TelegramConfig.from_env()` in `app/integrations/telegram/__init__.py`:

| Variable | Meaning | Default |
|---|---|---|
| `TELEGRAM_ENABLED` | master switch for send + poll | `false` |
| `TELEGRAM_BOT_TOKEN` (or `TELEGRAM_API_KEYS`) | Bot API token | unset |
| `TELEGRAM_ALLOWED_CHAT_IDS` | comma-separated allowlist; messages from other chats are ignored | empty |

Send path: `send_message(text, chat_id=...)` posts to the Bot API
(used by the notify dispatcher). Long replies are chunked under the
4096-character limit with a per-chat flood guard. `send_voice(text, ...)`
synthesises speech and uploads it as a Telegram voice bubble (OGG/Opus).

Chat path: `TelegramPoller` long-polls `getUpdates` and routes each
allowed message through the chat pipeline, replying in-thread. Voice and
audio attachments are downloaded via `getFile` and transcribed locally
before handling, so talking to the bot works like typing to it.

**HITL approval from the phone (ADR-017, Sprint 8.4):** `/approve` and
`/deny` decide the newest pending human-in-the-loop approval — a paused
DESTRUCTIVE step or worker request — through the shared
`_approve_pending_via_registry` helper (`app/adapters/http/router.py`).
`/approve <plan_id> <step_id>` targets a specific one. The decision
resumes the plan (approve) or skips the step (deny) exactly like
`POST /api/v1/hitl/approve`.

Enablement (see also `docs/N8N-SETUP.md` §Telegram): set the three
variables above, send the bot a message from the operator chat, and add
that chat's ID to the allowlist. Until the ID is known the n8n Telegram
node stays disabled on purpose.

### WhatsApp — send-only + template rule

`WhatsAppConfig.from_env()` in `app/integrations/whatsapp/__init__.py`:

| Variable | Meaning | Default |
|---|---|---|
| `WHATSAPP_ENABLED` | lets the notify dispatcher use it | `false` |
| `WHATSAPP_TOKEN` | permanent access token | unset |
| `WHATSAPP_PHONE_ID` | sending Phone Number ID from the Meta dashboard | unset |
| `WHATSAPP_TO` | operator's chat number | unset |
| `WHATSAPP_TEMPLATE` | template name for first contact | `hello_world` |

Meta's rule, enforced by the module layout: the **first** contact must
use an approved template (`send_template`), because no 24-hour
conversation window exists yet. `send_message` sends free-form text and
needs an open window. There is no inbound/poll path — WhatsApp is
send-only; replies from the operator do not re-enter JARVIS.

Setup pointer: create the Meta app, attach a number, approve a template,
export the five variables above, then test with
`channels: ["whatsapp"]` on `POST /api/v1/notify/`.

### Email — read / send / reply / search

`prefix="/api/v1/emails"` in `app/adapters/web/email_routes.py`,
backed by `app/integrations/email/client.py` (IMAP/SMTP):

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/emails/?folder=INBOX&limit=50&unread_only=false` | list (read) |
| `GET /api/v1/emails/search?query=...&limit=20` | search |
| `GET /api/v1/emails/{email_id}` | read one |
| `POST /api/v1/emails/` `{"to","subject","body"}` | send |
| `POST /api/v1/emails/{email_id}/reply` `{"body"}` | reply |

Connection env (defaults are Gmail-shaped, override for any provider):

| Variable | Default |
|---|---|
| `JARVIS_EMAIL_IMAP_HOST` / `JARVIS_EMAIL_IMAP_PORT` | `imap.gmail.com` / `993` |
| `JARVIS_EMAIL_SMTP_HOST` / `JARVIS_EMAIL_SMTP_PORT` | `smtp.gmail.com` / `587` |
| `JARVIS_EMAIL_ADDRESS` / `JARVIS_EMAIL_PASSWORD` | unset |

### Brief — generate / deliver (incl. push)

`prefix="/api/v1/brief"` in `app/adapters/web/brief_routes.py`:

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/brief/` | generate and return the brief JSON |
| `POST /api/v1/brief/deliver` | generate **and** deliver; returns `{"brief","delivery_results"}` |
| `GET /api/v1/brief/status` | enabled flag, time, delivery channels |

`BriefConfig.from_env()` in `app/integrations/brief/__init__.py`:

| Variable | Meaning | Default |
|---|---|---|
| `JARVIS_BRIEF_ENABLED` | master switch | `false` |
| `JARVIS_BRIEF_TIME` | local generation time | `08:00` |

The brief has four sections — Memory, Pending Approvals, Recent Activity, and
**Email** (Sprint 9.2: top unread headlines per configured mailbox via
`configured_accounts`). Delivery channels: `push`, `telegram` (spoken voice
note), `email`, `slack` (comma-separated in `JARVIS_BRIEF_DELIVERY`).

**Scheduled delivery (Sprint 9.3):** `scripts/deliver_brief.py` generates and
delivers, then exits non-zero unless a channel succeeded. The systemd timer
`scripts/jarvis-brief.timer` fires it daily at 08:00; install with:
`cp scripts/jarvis-brief.{service,timer} ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now jarvis-brief.timer`.
Test on demand: `JARVIS_BRIEF_DELIVERY=telegram .venv/bin/python scripts/deliver_brief.py`.
| `JARVIS_BRIEF_DELIVERY` | comma-separated channels: `slack`, `email`, `push` | `slack` |
| `JARVIS_BRIEF_SLACK_WEBHOOK` | incoming-webhook URL for `slack` delivery | unset |
| `JARVIS_BRIEF_EMAIL` | recipient for `email` delivery | unset |

`push` delivery reuses `PushService`, so a delivered brief lands on the
phone exactly like any other push notification (subscribe first — see
`docs/MOBILE_ACCESS.md`).

### Push — subscribe (VAPID)

Full flow lives in `docs/MOBILE_ACCESS.md`; the contract here:

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/v1/push/vapid-public-key` | none (public by design) | browser fetches key before any credential exists |
| `POST /api/v1/push/subscribe` | API key | register a `PushSubscription` |
| `DELETE /api/v1/push/unsubscribe` | API key | remove by endpoint |
| `POST /api/v1/push/test` | API key | send a test notification |

Server env: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`,
`VAPID_CLAIMS_EMAIL` (default `mailto:jarvis@localhost`). Without keys
the service skips with `VAPID key not configured` instead of failing.

## Defaults

- Notify defaults to `["push"]` when no `channels` are given.
- Brief defaults to disabled, time `08:00`, delivery `slack`.
- WhatsApp template defaults to `hello_world`; Telegram and WhatsApp
  integrations default to disabled until their tokens are set.
- Telegram replies are rate-limited to one per 1.5 s per chat.

## Failure Modes

| Symptom | Cause | Fix |
|---|---|---|
| `{"push": {"success": false, "error": "VAPID key not configured"}}` | VAPID env unset | set `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY`, restart |
| `{"telegram": {"success": false, ...}}` on notify | bot token missing/disabled | set `TELEGRAM_ENABLED=true` + `TELEGRAM_BOT_TOKEN` |
| `{"whatsapp": {"success": false, ...}}` on notify | token/phone/to missing | export the five `WHATSAPP_*` vars |
| WhatsApp first message never arrives | no open 24h window | use `send_template` (approved template) first |
| Telegram bot ignores a chat | chat ID not in `TELEGRAM_ALLOWED_CHAT_IDS` | add the operator chat ID |
| Email routes 500 | IMAP/SMTP unreachable or creds wrong | check `JARVIS_EMAIL_*` vars and provider app-password |
| Brief `deliver` reports `slack: false` | `JARVIS_BRIEF_SLACK_WEBHOOK` unset | set the webhook URL |
