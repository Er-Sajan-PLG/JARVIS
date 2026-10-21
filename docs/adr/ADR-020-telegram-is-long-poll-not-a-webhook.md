# ADR-020: Telegram is long-poll, not a webhook

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-10-21

> Drift trap for this type: Being *edited* to look correct in hindsight. An ADR that is rewritten to match current reality destroys the only record of why the decision was made.

---

## Context

The Telegram integration is **two-way**: alerts out, and the operator's own chat
in. The outbound half is trivial — a POST to the Bot API. The inbound half is
the one that needed a decision, because Telegram offers exactly two ways to
receive messages and they are mutually exclusive for a given bot token.

The constraint is the deployment model. JARVIS runs behind **Tailscale** and has
no public HTTPS endpoint. It never has. `app/integrations/telegram/__init__.py`
states the consequence in its own module docstring:

> It is deliberately polling, not a webhook: no public HTTPS endpoint is
> required, which keeps the Tailscale-only deployment model intact.

Two further properties were required and are implemented:

- **Only allowlisted chats are answered.** `TelegramConfig.from_env` reads
  `TELEGRAM_ALLOWED_CHAT_IDS`; `_handle_update` drops anything else. The
  docstring gives the reason: *"everyone else is ignored silently (no oracle for
  scanners)"* — an unknown chat learns nothing about whether the bot exists or
  is listening.
- **Conversations have memory.** Each chat is keyed to its own session id,
  `telegram:<chat_id>`, and routed through the same `/api/chat` pipeline the web
  console uses (`TelegramPoller._answer` calls
  `app.adapters.web.router.chat`).

## Decision

**Long-poll `getUpdates` in a background asyncio task. Do not register a
webhook.**

The poller is started from the server lifespan when `TELEGRAM_ENABLED=true` and
a token is present. It answers only allowlisted chats, transcribes voice notes
locally before handling them, and routes each message through the web chat
pipeline under a per-chat session.

## Alternatives considered

1. **A webhook with a public HTTPS callback.** This is what Meta requires for
   WhatsApp and what most Telegram bots use. Rejected: it needs an inbound
   public endpoint, which means either exposing the host or putting a tunnel in
   front of it. That single change would invalidate the deployment model for the
   whole application, not just this integration — to gain nothing but lower
   latency on a personal assistant that is not latency-sensitive.

2. **A webhook terminated at a Cloudflare Worker, forwarded over Tailscale.**
   Rejected as the worst of both: it adds a third-party hop that sees message
   content, and it still requires the tunnel it was meant to avoid.

3. **`getUpdates` polling but answering every chat that messages the bot.**
   Rejected: the bot's username is guessable, so any stranger could drive the
   assistant and spend model budget. Silent ignore was chosen over an error
   reply specifically so a scanner cannot use a response as an existence oracle.

4. **Webhook for inbound and polling only as a fallback.** Rejected: Telegram
   permits one delivery method per bot token at a time. Running both is not a
   supported configuration, and a fallback that cannot be exercised is a claim
   the code cannot keep.

## Consequences

### Positive

- **No inbound port, no certificate, no tunnel.** The integration works behind
  NAT because it only ever makes outbound requests.
- **The allowlist is the only thing standing between a stranger and the agent**,
  and it fails closed: an unknown chat gets no reply at all.
- **Voice notes work without a second transport.** `_transcribe_message`
  downloads the attachment via `getFile` and transcribes it locally with
  faster-whisper before the text reaches the chat pipeline, so a voice message
  takes the identical path to a typed one.
- **The approval loop works from a phone.** `/approve` and `/deny` decide the
  newest pending HITL approval via the approval registry (ADR-017), and are
  handled *before* the general chat route so the words are not swallowed by the
  model.

### Negative

- **Latency is bounded by the long-poll.** `_get_updates` passes `timeout: 30`,
  so a reply can wait up to the poll cycle. Acceptable for a personal assistant;
  it would not be for a customer-facing bot.
- **A leaked token fully impersonates the bot** — it can both send as JARVIS and
  read its updates. The token is a bearer secret in the environment with no
  scoping, and no rotation procedure has been tested. Recorded as **RISK-018**
  (accepted).
- **One poller per token.** Running two instances splits the update stream
  between them rather than duplicating it, so messages would be answered by
  whichever instance won the `offset` race.
- **The bot token cannot be used with a webhook** while this runs, so adopting a
  webhook later is a migration, not an addition.

## Related

- `docs/ACCEPTED_RISKS.md` **RISK-018** — the token's blast radius, accepted.
- `app/integrations/telegram/__init__.py` — the implementation.
- **ADR-011** — the tool-safety and HITL gate that `/approve` and `/deny` decide
  against.
- **ADR-017** — subagent orchestration; the approval commands were added for it
  (Sprint 8.4).
