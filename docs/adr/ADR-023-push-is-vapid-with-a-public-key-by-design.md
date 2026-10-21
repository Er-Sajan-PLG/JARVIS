# ADR-023: Push is VAPID, and the public key is exposed by design

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-10-21

> Drift trap for this type: Being *edited* to look correct in hindsight. An ADR that is rewritten to match current reality destroys the only record of why the decision was made.

---

## Context

The phone needs to be reachable when the app is closed — that is what makes a
morning brief useful rather than a thing you have to remember to open. Web Push
is the only mechanism available to a PWA that does not require a third-party
push service account, and it requires **VAPID**: the server holds an asymmetric
key pair and signs each push.

That produces a question with a non-obvious answer: the browser must know the
**public** key *before* it can subscribe, but subscribing is an authenticated
action. If the endpoint that hands out the public key required a key, the client
could never bootstrap.

`app/adapters/web/push_routes.py` resolves this by splitting the surface into
two routers, and states the reasoning inline:

> VAPID public key is public by design (the browser needs it before any
> [authentication]...). Gating it would make push uninstallable.

Subscriptions persist to `data/push_subscriptions.json` so a restart does not
silently drop every registered device.

## Decision

**VAPID Web Push, with exactly one unauthenticated endpoint — the public key.**

- `push_public_router` — `GET /api/v1/push/vapid-public-key`, **no auth**, returns
  `{"publicKey": ...}`.
- `push_router` — **auth via `validate_api_key`**, carrying
  `POST /subscribe`, `DELETE /unsubscribe`, `POST /test`, `GET /status`.
- The **private** key comes from `VAPID_PRIVATE_KEY` in the environment and is
  never returned by any route.
- Subscriptions are persisted to disk; an endpoint that returns `410` or an
  "expired" error is removed automatically during a send.

## Alternatives considered

1. **Gate the public-key endpoint behind the API key.** Rejected as
   self-defeating: the browser needs the key in order to subscribe, so requiring
   the key to fetch it means push can never be installed. The module comment
   names this outcome.

2. **Ship the public key inside the client bundle instead of serving it.**
   Rejected: it hardcodes a value that must be regenerated whenever the VAPID
   pair is rotated, so rotation would require rebuilding and redistributing the
   client. Serving it keeps rotation a server-side change.

3. **An FCM or APNs account instead of VAPID.** Rejected: it adds a third-party
   service and its credentials to a self-hosted personal assistant, and FCM is
   not usable for a plain PWA without a native wrapper.

4. **Ephemeral subscriptions, no persistence.** Rejected explicitly: without
   `data/push_subscriptions.json`, *"every reboot would silently drop every
   phone's registration and push notifications would stop working until the user
   re-opened the app"*.

5. **Retain subscriptions that fail to send.** Rejected: a `410` is the push
   service stating the subscription is gone, so keeping it means retrying a dead
   endpoint forever. The send loop prunes them.

## Consequences

### Positive

- **Push works on a self-hosted server with no third-party push account.** Only
  the browser's own push service is involved, which is unavoidable for Web Push.
- **The unauthenticated surface is exactly one read-only endpoint** that returns
  a value intended to be public. The authenticated router is untouched by the
  exception.
- **Subscriptions survive restarts**, which is the difference between a
  notification channel and a thing that works only until the next deploy.
- **Dead endpoints self-prune**, so the subscription file does not accumulate
  devices that can never be reached.

### Negative

- **A leaked VAPID private key lets anyone push to every subscriber.** There is
  no key-rotation runbook. Recorded as **RISK-021** (accepted).
- **The subscription file is a list of endpoints plus their keys**, stored in the
  data directory rather than a database. It is not encrypted, and it is only as
  protected as the data directory.
- **One unauthenticated route must stay that way.** A future reader who "fixes"
  the missing `Depends(validate_api_key)` on the public router breaks push
  entirely — the inline comment is the only thing preventing that, which is why
  this ADR exists.
- **Web Push behaviour is browser-dependent.** Delivery is best-effort and the
  server cannot confirm that a notification was displayed.

## Related

- `docs/ACCEPTED_RISKS.md` **RISK-021** — the VAPID private key's blast radius.
- `app/adapters/web/push_routes.py` — the two-router split.
- `app/integrations/push/__init__.py` — `PushService`, persistence, and the
  stale-endpoint pruning.
