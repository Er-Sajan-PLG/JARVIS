# ADR-012 — One GitHub identity per function, short-lived tokens


**Status**: ACTIVE
**Last Updated**: 2026-09-11
- Status: Accepted
- Date: 2026-09-11
- Amends: RISK-015 (resolved at the CI layer)
- Related: ADR-011, docs/CI-TOKEN-PERMISSIONS.md

## Context

The local CI gate runs from one process (`scripts/ci_bridge.py`) that resolves a
single token and uses it for two different API jobs:

- `GET /repos/{o}/{r}/pulls` — needs **Pull requests: Read**
- `POST /repos/{o}/{r}/statuses/{sha}` — needs **Commit statuses: Read and write**

On 2026-09-11 the permissions were split across two tokens, so whichever one won,
half the job failed. That is RISK-015, and it is why the gate printed
`statuses=8` while GitHub received nothing.

The immediate fix (applied and verified) was to add **Pull requests: Read** to
`JARVIS_CI_TOKEN` and place it in `.ci-bridge.env`, because a systemd
`EnvironmentFile` variable beats every file in `TOKEN_FILES`. Read-back confirms
it: `GET /commits/<sha>/status` returns `state=success, total_count=8`.

The owner then asked the wider question: whether to run a differently-scoped token
per workflow, "because i believe we are going to need a lot of those". That is the
right instinct, and this ADR records the answer.

## Decision

**Target state: one GitHub App per function, installed only on the repositories
that function touches, minting 1-hour installation tokens on demand. The process
stores an App private key, never a usable token.**

**Present state: keep the working fine-grained PAT and migrate function by
function.** Do not tear out a verified-working path to chase a design. The PAT is
a bridge, not the destination.

## Why an App, not a PAT per workflow

| | fine-grained PAT | GitHub App installation token |
|---|---|---|
| lifetime | 30–366 days, or none; manual expiry | **1 hour**, automatic |
| rotation | manual, per token | automatic, by minting |
| tied to a person | **yes** — breaks when that user loses repo access | no — survives role/staff changes |
| audit trail | "the human did it" | attributed to the **app** |
| granularity | per-repo permissions | per-repo, per-installation permissions |
| scale ceiling | **50 fine-grained PATs per user** | no equivalent low ceiling |
| revocation | revoke the PAT | uninstall, or revoke the token |
| setup cost | low | moderate (App registration, JWT signing) |

Two rows decide it for something that will grow: the **50-PAT ceiling** and the
**user-tie**. "A lot of those" is exactly where PATs stop working, and a leaked
long-lived PAT is a standing liability while a leaked installation token is dead
in an hour.

## Function-to-identity map

Each row becomes its own App, with exactly the permissions in the right column.

| function | workflow / script | permissions |
|---|---|---|
| **CI publisher** | `ci_bridge.py` (JARVIS-CI-Local) | Contents: Read, Pull requests: Read, Commit statuses: Read and write |
| **Housekeeping** | JARVIS-Cleanup | Contents: Write (delete branches), Pull requests: Read and write (close stale), Actions: Read and write (delete old runs) |
| **Workflow editing** | PRs touching `.github/workflows/*` | Workflows: Read and write |
| **HITL approvals** | JARVIS-HITL | **none** — it talks to JARVIS with `JARVIS_API_KEY`, not to GitHub |
| **Interactive dev** | the human, `gh` CLI | whatever the human already has |

HITL needing no GitHub identity is the point: not every workflow needs a token,
and the default should be "prove you need one".

## Consequences

- **Good**: no manual rotation; compromise is time-boxed; audit shows the app, not
  a person; per-function blast radius.
- **Cost**: App registration, RS256 JWT signing, a mint step, and a cache (mint at
  most hourly).
- **Risk to watch**: the App private key is now the crown jewel — 0600 file or a
  systemd credential, never in git, never printed.

## Migration path

1. **Done (2026-09-11)**: `JARVIS_CI_TOKEN` with the three CI permissions, in
   `.ci-bridge.env`. Verified publishing (`published=8/8`, read-back `total_count=8`).
2. **Next**: create the `jarvis-ci` App; add `scripts/mint_app_token.py`
   (private key → JWT → installation token, cached for the hour); make
   `load_token()` prefer the App token when App credentials exist, PAT as fallback.
3. **Then**: `jarvis-cleanup` App — the function that *destroys* things most
   deserves its own narrow identity.
4. **Finally**: drop the PATs; `.ci-bridge.env` holds App ids and key paths, not
   usable tokens.

> **Status correction (2026-09-13, path-checked against the tree).** Step 2's
> *code* half is done, under a different filename than this ADR names: the minter
> is `scripts/github_app_token.py` (RS256 JWT → installation token, 1-hour cache),
> and `scripts/ci_bridge.py::load_token()` already prefers an App token when one
> is configured, raising rather than silently falling back when it is configured
> but broken. What remains is **not code**: the App must be registered at
> github.com/settings/apps, a website action only the account owner can perform —
> tracked as **RISK-016**. Steps 3 and 4 remain open. The `mint_app_token.py`
> name was never created; do not look for it.

## Alternatives rejected

- **One broad PAT for everything** — blast radius of every permission at once, one
  expiry breaks every workflow together, 50-token ceiling, audit blames a human.
- **GitHub Actions `GITHUB_TOKEN`** — Actions is billing-blocked on this private
  repo; that is why the local plane exists at all.
- **Deploy keys** — git access only; cannot publish commit statuses or list PRs.
- **OAuth app tokens** — long-lived, broad scopes, same user-tie as a PAT.

## The invariant every future auth change must preserve

A credential's permissions must be a **superset of that function's needs and a
subset of its entitlement** — and the failure when it is not must be **loud**.
The false-green that hid this for weeks is why `ci_bridge.py` now reports
`published=N/M` and exits non-zero on a publish failure. Any auth refactor must
keep that: **prove the effect, not the call.**
