# ADR-021: WhatsApp is send-only, and there is no inbound webhook

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-10-21

> Drift trap for this type: Being *edited* to look correct in hindsight. An ADR that is rewritten to match current reality destroys the only record of why the decision was made.

---

## Context

WhatsApp was added as a **notification** channel, not a conversation channel —
the brief and alerts should arrive where the operator already is.
`app/integrations/whatsapp/__init__.py` states the boundary in its own
docstring:

> One direction only: JARVIS → operator. Sending is plain outbound HTTPS, so it
> works behind NAT with no public endpoint. Receiving (webhooks) is NOT
> implemented: Meta requires a public HTTPS callback URL, which a Tailscale-only
> deployment does not have.

This is the same deployment constraint that produced ADR-020 for Telegram, but
it resolves differently, because the two platforms are not symmetric. Telegram
offers `getUpdates` — a pull API needing no inbound endpoint. **WhatsApp offers
no equivalent.** The Cloud API delivers inbound messages only by webhook, so the
choice was never *poll or webhook*; it was *webhook or nothing*.

Meta adds a second constraint that shapes the send path: business-initiated
conversations must open with an **approved template**, and only after the
operator replies does a 24-hour customer-service window open for free-form text.
Both paths are implemented — `send_template` and `send_message`.

## Decision

**Send-only. No inbound webhook, and no attempt to emulate one.**

`send_template` is the first-contact path; `send_message` is the free-form path
for use inside an open 24-hour window. Both POST to
`https://graph.facebook.com/v21.0/<phone_id>/messages` with a bearer token, and
both return `False` rather than raising when the platform rejects the request.

## Alternatives considered

1. **A webhook, as Meta requires.** Rejected for ADR-020's reason: it needs a
   public HTTPS callback, which would invalidate the deployment model for the
   whole application. Unlike Telegram there is no pull API to fall back on, so
   this alternative means accepting the trade or not shipping the channel.

2. **A Cloudflare Worker terminating the webhook and forwarding over Tailscale.**
   Rejected: it puts a third party in the path of message content to gain a
   feature that was never requested. This channel is for notifications.

3. **Skip WhatsApp and use Telegram alone.** Rejected — it is the operator's
   primary messaging app, which is precisely why alerts are worth pushing there.

4. **Use the 24-hour test token to avoid the permanent-token setup.** Rejected
   explicitly by the module docstring: *"never the 24h test token for anything
   that must keep working"*. A channel that silently stops after a day is worse
   than one that was never wired.

## Consequences

### Positive

- **Works behind NAT with no public endpoint**, like every other outbound
  integration here.
- **No inbound attack surface at all.** There is no webhook route to
  authenticate, rate-limit or verify a signature on, because there is no webhook.
- **The template-plus-window rule is implemented, not fought.** The integration
  follows Meta's actual delivery rule rather than assuming free-form always works.

### Negative

- **JARVIS can never receive a WhatsApp message.** No conversational use, no
  commands, no approvals — the channel is strictly one-way. That is a permanent
  asymmetry with Telegram, and the reason the two are documented separately
  rather than as one "comms" decision.
- **The token is a long-lived permanent System User token.** A leak lets anyone
  send as the business number until it is revoked in the Meta dashboard.
  Recorded as **RISK-019** (accepted by design).
- **Migrating the real number is irreversible.** The docstring records that the
  number must be deleted from the WhatsApp Business app first, and that existing
  app chats do not carry over.
- **Free-form sends fail outside the 24-hour window.** The caller must know
  whether the window is open; the API returns an error rather than opening one.

## Related

- `docs/ACCEPTED_RISKS.md` **RISK-019** — the permanent token's blast radius,
  accepted by design.
- `app/integrations/whatsapp/__init__.py` — the implementation and the setup
  sequence.
- **ADR-020** — the Telegram decision. Same deployment constraint, opposite
  resolution, because Telegram has a pull API and WhatsApp does not.
