# ADR-025: tgcall runs outside the server auth boundary

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-10-21

> Drift trap for this type: Being *edited* to look correct in hindsight. An ADR that is rewritten to match current reality destroys the only record of why the decision was made.

---

## Context

Live voice calls were a Sprint 11 goal: the operator should be able to ring JARVIS
and talk to it. The hard part is not the audio loop — it is that **placing a
Telegram call is not something a bot can do**. The Bot API has no voice-call
surface. Reaching calls requires authenticating as a **user session** through
MTProto, which grants the same access as the account itself, not the narrower
access a bot token grants.

The second constraint is tooling. The working call stack is JavaScript: GramJS
for the MTProto session and `gram-tgcalls`/`tgcalls` for signaling and media.
`tgcall/package.json` depends on exactly `gram-tgcalls`, `telegram` and
`tgcalls`, and runs on Node 18 (the README notes a `wrtc` caveat on that runtime).

So `tgcall/` is a **Node sidecar**, not server code. It is two files with clear
roles:

- `login.js` — one-time interactive login. Writes the session to
  `data/tgcall.session` with **mode `0o600`**.
- `call.js` — logs in as the operator, calls the operator's own account so the
  phone rings, then runs a turn loop entirely through JARVIS HTTP:

  ```
  call audio in  -> POST /api/v1/voice/stt  -> text
  text           -> POST /api/chat          -> reply (fast model)
  reply          -> POST /api/v1/voice/tts  -> mp3 -> played into the call
  ```

It reaches JARVIS at `JARVIS_URL` (default `http://127.0.0.1:8000`) and presents
`JARVIS_API_KEY` — the console key — on those requests, like any other client.

## Decision

**Keep live calls in a separate Node sidecar that authenticates as the operator
and calls JARVIS's existing HTTP endpoints. Do not put telephony in the FastAPI
process, and do not extend the server's auth model to cover it.**

The sidecar is a client of JARVIS, not part of it. Its Telegram identity is the
operator's user session; its JARVIS identity is the console API key.

## Alternatives considered

1. **Use a bot token instead of a user session.** Rejected — and not really
   available. Bots cannot place calls, so a user session is a *requirement* of
   the feature rather than a choice. This is the single most important fact about
   this decision: the broad credential is not an accident of implementation.

2. **Implement the call stack inside FastAPI, in Python.** Rejected: the
   maintained call libraries are JS. There is no Python path with working
   signaling **and** media, so this would mean writing the media stack.

3. **Use a cloud telephony provider (Twilio or similar).** Rejected: it adds a
   third party, a per-minute cost and a phone number, to reach the operator's own
   Telegram account — which the operator can already call for free.

4. **Put the sidecar behind the server's authentication.** Rejected as
   meaningless: the sidecar *is* the operator. Requiring it to authenticate to
   JARVIS does not constrain anything, because it already holds the console key
   by design. The real credential of concern is the Telegram session, and that
   lives in Telegram's protocol, not in JARVIS's auth model.

5. **Persist the session in the server's data directory under the server's
   lifecycle.** Rejected: the file is created by the sidecar's login flow and
   would then be managed by two processes. Keeping it in `data/` while owned by
   `login.js` is the smaller surface.

## Consequences

### Positive

- **No telephony code in the server.** The audio loop reuses
  `/api/v1/voice/stt`, `/api/chat` and `/api/v1/voice/tts` (ADR-022) exactly as
  the phone client does, so there is one voice implementation, not two.
- **A sidecar crash does not take JARVIS down**, and the server can be restarted
  without dropping a call.
- **The session file is written `0o600`**, so it is not world-readable on the
  host.

### Negative

- **The session credential is far broader than a bot token.** If
  `data/tgcall.session` leaks, the holder has full account access — not just the
  ability to send messages. This is the highest-severity risk in the
  comms/voice/mobile group: **RISK-023, HIGH**, accepted by the owner as a secret
  call. No audit of where the file is stored or what backs it up exists yet.
- **`tgcall/` has no tests.** `package.json`'s `test` script is the npm default
  stub, `echo "Error: no test specified" && exit 1`. Nothing in CI exercises this
  code, so it is verified by running it, not by the gate.
- **The `tgcalls` API drifts between versions**, which is why `check-api.js`
  exists and why `call.js` records that the exact `VoiceCall` attach call must be
  pinned by running it first.
- **It is outside the server's process and auth boundaries.** A bug in the
  sidecar is invisible to the server's logging, health checks and gate.
- **It requires a Node runtime alongside the Python one**, with a `wrtc`
  caveat on Node 18.

## Related

- `docs/ACCEPTED_RISKS.md` **RISK-023** — the user-session credential, HIGH,
  accepted by the owner.
- `tgcall/login.js`, `tgcall/call.js`, `tgcall/check-api.js` — the sidecar.
- **ADR-022** — the voice endpoints the sidecar drives.
- **ADR-020** — the bot-token integration, whose credential is deliberately
  narrower than the one this decision requires.
