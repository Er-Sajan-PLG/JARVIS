# ADR-022: Voice ingress is bounded local STT plus Edge TTS

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-10-21

> Drift trap for this type: Being *edited* to look correct in hindsight. An ADR that is rewritten to match current reality destroys the only record of why the decision was made.

---

## Context

The phone clients — the PWA and the Android build — need to speak and listen.
That means the server accepts **uploaded audio**, which is the only place in
JARVIS where a client can push an unbounded binary at the process. Everything
else is JSON.

Three constraints shaped the design, and
`app/adapters/web/voice_routes.py` records them:

- **No API key for either direction.** STT runs locally via faster-whisper; TTS
  uses Edge TTS. Neither needs a credential, so voice works on a machine that
  has no cloud speech account.
- **Keep the client simple and the server stateless.** The module docstring:
  *"Nothing streams — request/response keeps the phone client simple and the
  server stateless."*
- **Bound what a client can cost.** An upload is capped at **10 MB** (returns
  `413 "audio too large (10MB max)"`) and TTS input is capped at **2,000
  characters** (`text[:2000]`).

The routes are registered under `/api/v1/voice` with
`dependencies=[Depends(validate_api_key)]`, so the same console key that guards
the rest of the API guards audio ingress.

## Decision

**Local STT, Edge TTS, bounded inputs, request/response.**

- **STT**: faster-whisper, lazily loaded once per process, `tiny` model on CPU by
  default (`JARVIS_STT_MODEL` selects `base`/`small`). The model downloads on
  first use (~75 MB).
- **TTS**: Edge TTS, no key, voice selectable via `JARVIS_TTS_VOICE`.
- **Ingress bound**: 10 MB per upload, enforced before processing.
- **TTS bound**: 2,000 characters.
- **No streaming**: the client records, POSTs, and plays the returned audio.

## Alternatives considered

1. **A cloud STT provider** (Whisper API, Deepgram, Google Speech). Rejected:
   it adds a key, a per-request cost and a network dependency for a personal
   assistant, and it sends the operator's voice off the machine. Local
   faster-whisper was already a dependency of the Telegram voice path
   (ADR-020), so the marginal cost of reusing it was zero.

2. **Streaming STT/TTS** (websocket audio). Rejected for now: it moves state
   into the connection, complicates the phone client, and buys latency that a
   push-to-talk interaction does not need. The module docstring records the
   reasoning as a deliberate simplification rather than an omission.

3. **No size cap, trusting the client.** Rejected: an unbounded upload is a CPU
   exhaustion vector, and the cap is a two-line guard. It is the cheapest
   control in the subsystem.

4. **A duration ceiling as well as a size ceiling.** Considered and **not**
   implemented. A 10 MB ceiling bounds bytes, not decode time, so a
   highly-compressed long recording can still cost more CPU than its size
   suggests. Recorded as the residual in RISK-020 rather than claimed as covered.

5. **Content review of uploaded audio.** Rejected: there is one operator, and
   the audio is going to a model that is already trusted with the operator's
   text. A moderation pass would add a dependency to police the operator.

## Consequences

### Positive

- **No credentials in either direction.** Voice works on a machine with no cloud
  speech account, and the audio never leaves the host for transcription.
- **The ingress bound is explicit and returns a clear error.** A too-large
  upload is a `413` with a reason, not a timeout.
- **Temp files are `delete=True`**, so uploads do not accumulate on disk.
- **Auth is inherited, not reimplemented.** The route group depends on
  `validate_api_key`; there is no second auth path to keep correct.

### Negative

- **No duration ceiling and no content review.** A large-but-under-10 MB upload
  costs CPU. It cannot execute code, but it can occupy the worker. Recorded as
  the residual in **RISK-020** (accepted, partial gap).
- **The first request is slow.** The model downloads (~75 MB) on first use and
  is cached in-process only, so a restart pays it again.
- **`tiny` is the default, so accuracy is modest.** Raising it is an env change
  and a CPU cost, not a code change.
- **Request/response means no barge-in.** The operator cannot interrupt
  playback; the exchange is turn-based.

## Related

- `docs/ACCEPTED_RISKS.md` **RISK-020** — upload processing, accepted with the
  duration residual named.
- `app/adapters/web/voice_routes.py` — the implementation.
- **ADR-020** — the Telegram voice path reuses the same local transcription
  approach for voice notes.
