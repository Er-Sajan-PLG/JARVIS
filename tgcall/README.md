# tgcall — Telegram p2p voice-call sidecar (Sprint 11.4)

Bridges JARVIS to a real Telegram voice call (ring → speak → think → speak),
driven by a **userbot** (your own account via `api_id`/`api_hash`), not the
Bot API (bots cannot place calls).

## Status — HONEST

| Layer | State |
|---|---|
| Media stack loads (`tgcalls`/`wrtc`) | ✅ verified earlier |
| DH crypto (2048-bit safe prime, AES-ready keys, fingerprint) | ✅ `test-crypto.js` passes |
| MTProto call signaling (`requestCall`/`acceptCall`/`confirmCall`/`discardCall`) | ⚠️ implemented, **not live-tested** (needs an answered call) |
| SRTP audio bridge → JARVIS STT/TTS | ❌ **not implemented** — the remaining blocker |

The signaling and crypto are foundation. A working end-to-end call still needs
the media layer (encrypted SRTP → decode → JARVIS STT, and TTS → encode →
SRTP) plus live debugging against a real answered call, which cannot be done
in a single session.

## Files

- `lib/crypto.js` — Telegram VoIP DH (fixed 2048-bit prime, `g_a_hash` =
  SHA-256 of padded `g^a`, shared-key + fingerprint).
- `lib/signaling.js` — call state machine over GramJS (`phone.requestCall`,
  `acceptCall`, `confirmCall`, `discardCall`).
- `test-crypto.js` — proves both DH sides derive the identical shared key.
- `login.js` — creates the userbot session (`data/tgcall.session`).
- `call.js` — turn loop skeleton (dial → STT → JARVIS chat → TTS → speak).
- `check-api.js` — pins the installed `gram-tgcalls` API surface.

## Run

Requires `api_id`/`api_hash` from https://my.telegram.org and a one-time login:

```bash
TG_API_ID=.. TG_API_HASH=.. node login.js      # once, pastes the code
node test-crypto.js                            # verify crypto
```

## Ethics / risk

This uses a **userbot** on your own account — automation on a personal
account is a gray area. Safe here because it only ever calls *you*. The voice
notes path (`send_voice`, Bot API) is the fully-supported alternative and
already works.