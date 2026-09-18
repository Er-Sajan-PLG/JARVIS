# ADR-016 — Documentation coverage blocks the push

**Status**: ACTIVE
**Type**: adr
**Last Updated**: 2026-09-18
**Reviewed**: 2026-09-18

- **Date**: 2026-09-18
- **Author**: JARVIS session (operator-directed lockdown)
- **Related**: `scripts/check_doc_coverage.py`, `tests/unit/test_doc_coverage.py`,
  `githooks/pre-push`, `scripts/ci_gate.py` (`gate_doc_coverage`),
  `docs/DOC-GOVERNANCE.md`, ADR-014
- **Supersedes**: nothing. Extends ADR-014 (machine-checked facts) from
  *numbers* to *coverage*: it is no longer possible to land a feature with
  zero docs.

## Context

The 2026-09-18 docs audit found every doc gate green while ~40 claims were
stale and 12 shipped features (notify dispatcher, voice endpoints, Telegram
two-way + voice notes, WhatsApp send-only, runner comms tools, chat email /
brief injection, brief→push, mic/speaker UI, self-healing connection, offline
banner, wake lock, Capacitor APK, tgcall sidecar) had zero documentation.
Root causes, all verified in code:

- `scripts/check_docs.py` scans `docs/**` only — `app/`, `frontend/`,
  `mobile/`, `tgcall/` are never inputs.
- `scripts/board/review.py` scraped routes only from
  `app/adapters/web/router.py` + `app/adapters/http/router.py` (missing
  `*_routes.py` by glob), and its capability check
  is a no-op.
- The pre-push hook exited 0 unconditionally — pushes could never be refused
  for docs.

## Alternatives considered

- **Convention + review only (status quo).** Rejected: the audit proved it
  fails silently — green gates, 40 stale claims, 12 undocumented features.
- **Weekly doc-scrub sessions.** Rejected: toil without enforcement; drift
  regrows between scrubs and nobody owns the delta.
- **Block in CI only (no pre-push hook).** Rejected: local pushes to a
  non-PR remote bypass CI entirely; the refusal must live on the push path
  itself. CI enforcement stays as the second layer, not the only one.
- **Allow bypass flag (`--no-verify` style).** Rejected: a bypass used once
  becomes the workflow. No flag exists on purpose.

## Decision

1. **Coverage gate** (`scripts/check_doc_coverage.py`, `--strict`): three
   censuses computed from the live tree — module→`Source` bindings, served
   routes vs `API_CONTRACT.md`, `os.getenv` reads vs `CONFIG.md`. Any
   finding fails. It found 164 findings on arrival; zero at acceptance.
2. **Tests pin the gate** (`tests/unit/test_doc_coverage.py`): the full
   tree must satisfy its own gate — no grandfathering. One missing doc
   fails the suite, which fails the pipeline.
3. **Push refusal** (`githooks/pre-push`): runs `check_docs --strict`,
   `check_doc_coverage --strict`, and the doc-coverage tests before the
   release tagging. Any failure exits non-zero: the push does not happen.
   Deliberately no bypass flag.
4. **CI enforcement** (`gate_doc_coverage` in `scripts/ci_gate.py`): same
   script runs in the pipeline so PRs fail identically.

## Consequences

### Positive

- "A feature with zero docs" is now a mechanical impossibility, not a
  convention. The 2026-09-18 class of drift cannot recur.
- Gate bugs are found by the gate's own tests (three collector bugs were
  fixed during construction: `environ.get` as routes, `*router*` missing
  `*_routes.py`, single-token Source parsing).

### Negative

- Push latency grows by the gate runtime (seconds) plus the doc-test subset.
- `Source` bindings become load-bearing: renaming a module without updating
  the bound doc fails the push. This is intended (move the code, the doc
  goes red instead of quietly stale).
- Prose quality is still unjudged — the gate measures presence and
  endpoint/env truth, not whether the paragraph is good. Review owns that.

## Migration Plan

None required — the gate shipped green against the refreshed docs in the
same change (`0902b27`).
