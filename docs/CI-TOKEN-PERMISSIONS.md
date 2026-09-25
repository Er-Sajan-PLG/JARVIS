# JARVIS CI — GitHub token permissions

**Status**: ACTIVE
**Type**: reference
**Source**: `scripts/ci_bridge.py`, `.ci-bridge.env` (not committed)
**Last Updated**: 2026-09-13
**Reviewed**: 2026-09-14

**Method**: every row below was measured with a live API probe against
`api.github.com` on 2026-09-13, not read off the GitHub UI. Token values are
never printed — only prefixes and SHA-256 identity hashes.

---

## 1. What changed on 2026-09-13

The owner added **Contents: Read and write** to the CI token. That is the
permission this document previously listed as the single blocker to letting the
local gate merge its own green PRs.

**Measured before → after, same token, same endpoint:**

| Probe | Before | After |
|---|---|---|
| `POST /repos/{o}/{r}/git/refs` (contents:write) | **403** | **201** |
| `PUT /repos/{o}/{r}/pulls/{n}/merge` (contents:write) | 403 | now permitted |
| `POST /repos/{o}/{r}/releases` (contents:write) | 403 | now permitted |
| `POST /repos/{o}/{r}/pulls/{n}/reviews` (pull_requests:write) | 403 | **200** |
| `POST /repos/{o}/{r}/issues/{n}/comments` (issues:write) | — | **201** |

The 201 on ref creation is the proof: contents:write is genuinely held, not just
absent from a 403 body. (The probe ref was deleted immediately; `DELETE` → 204,
then `GET` → 404.)

> **Note on the name `JARVIS_CI_N8N`.** No credential of that name exists. This
> was checked exhaustively on 2026-09-13: a recursive grep of the entire home
> directory (excluding dependency and cache trees) finds the literal string only
> in Hermes' own logs, in shell history, and in this document — never as an
> assignment in any env file, systemd unit, or n8n credential. The token that
> actually carries the CI permissions is **`JARVIS_CI_TOKEN`** in
> `/home/sajan/Projects/JARVIS/.ci-bridge.env`. It was re-verified live after the
> update and holds contents:write, pull_requests:write and issues:write.
> If a second token was created under a different name, no code path here
> references it.

---

## 2. The tokens on this machine, measured

Three distinct write-capable credentials exist. They are **not** interchangeable:

| Token | Stored in | Identity | list PRs | read statuses | publish statuses | contents:write |
|---|---|---|---|---|---|---|
| **CI token** | `.ci-bridge.env`, repo `.env` | `github_pat_11CAWY4NA…` (sha `5ab1adf1…`) | ✅ 200 | ✅ 200 | ✅ | ✅ **201** |
| **n8n GitHub credential** | n8n credential `github-api-auth` | `github_pat_11CAWY4NA…` (sha `35465799…`) | ✅ 200 | ❌ **403** | ❌ 403 | ✅ 201 |
| `gh` CLI | keyring (`gh auth`) | classic, `repo` scope | ✅ | ✅ | ✅ | ✅ |

The CI token and the n8n credential share a **prefix but differ by SHA** — they
are two different fine-grained PATs issued to the same account, with different
permission sets. The n8n credential notably **cannot read commit statuses**
(403), so it cannot publish the gate's <!--fact:context_count-->9<!--/fact--> contexts. It is used by the
`JARVIS-CI-Local` workflow only as an HTTP-header credential for the *bridge*
(`ci-bridge-auth`); it never talks to GitHub directly for status publication.

That is the design: **n8n holds no GitHub write capability for CI.** The bridge
in `scripts/ci_bridge.py` does the publishing, using its own token.

---

## 3. What the CI publisher needs

`scripts/ci_bridge.py` resolves one token via `load_token()` and uses it for
three jobs:

| Job | Call | Permission |
|---|---|---|
| Discover work | `GET /repos/{o}/{r}/pulls` | **Pull requests: Read** |
| Publish the verdict | `POST /repos/{o}/{r}/statuses/{sha}` | **Commit statuses: Read and write** |
| Merge a green PR (new) | `PUT /repos/{o}/{r}/pulls/{n}/merge` | **Contents: Read and write** |
| Fetch the merge result | `git fetch` of head + base | **Contents: Read** |

`JARVIS_CI_TOKEN` now holds **all four**. Repository access is scoped to
`Er-Sajan-PLG/JARVIS` only. No other token is required for CI.

### Resolution order

`load_token()` reads, in order:

1. **Environment** — an env var beats every file. `.ci-bridge.env` is a systemd
   `EnvironmentFile`, so the service gets `JARVIS_CI_TOKEN` from here first.
2. `TOKEN_FILES` in order: `~/Projects/.env`, `~/.hermes/.env`, repo `.env`.
3. A **configured GitHub App**, if `JARVIS_APP_ID` + key path are set — and if the
   App is configured but broken it **raises** rather than silently falling back
   to the PAT (RISK-015: a silent fallback is how a permission regression hides).

Verify with:

```bash
.venv/bin/python scripts/ci_bridge.py --check-auth
```

Expected: `source : /home/sajan/Projects/JARVIS/.ci-bridge.env:JARVIS_CI_TOKEN`.

---

## 4. Branch protection is NOT a token problem (re-confirmed 2026-09-13)

This is the most-misread item in this repo, so it is stated plainly.

Two **different** 403s come back from the same endpoint:

| Caller | 403 body | Wall |
|---|---|---|
| `JARVIS_CI_TOKEN` (fine-grained) | `Resource not accessible by personal access token` | token scope — *not* the blocker |
| `gh` CLI (**classic `repo`**, which includes `administration:write`) | `Upgrade to GitHub Pro or make this repository public to enable this feature.` | **plan** |

The second caller is not short of scope: `GET /collaborators/Er-Sajan-PLG/permission`
returns `"permission": "admin"` and GraphQL reports `viewerPermission: ADMIN`,
`viewerCanAdminister: true`. It still gets the *plan* message. Repository
**rulesets** are gated identically — `GET`/`POST /rulesets` return the same
upgrade message, so there is no ruleset escape hatch on a private Free repo.

**Conclusion: granting the CI token `administration: write` would not enable
branch protection.** The block is the GitHub plan. Tracked as **RISK-012**;
enforcement stays n8n-side (the gate publishes, the pipeline stops, a human does
not press merge). Do not spend time on token scopes here.

---

## 5. The Dependabot backlog, and what now unblocks it

Observed 2026-09-13: PRs **#44–#53 sat OPEN** — not failing, simply never merged:

- `gh pr view 50` → `mergeable: MERGEABLE`, `mergeStateStatus: CLEAN`
- `GET /commits/<head>/status` → `state: pending`, **0 statuses** — never gated
- `.governance/ci_bridge_state.json` listed gated PRs 25/36/51/52/53/57/58/59,
  but not 44–50, so the bridge never picked them up
- `PUT /pulls/50/merge` with the old token → **403** (`contents=write`)
- `allow_auto_merge: false`, and it cannot be enabled on this plan

So even a fully green Dependabot PR could not be merged by automation. With
Contents: Read and write now held, the remaining work is **local**: teach the
bridge to merge a PR whose gate conclusion is `success`. See
`docs/CI-GATE-SOTA.md` for the gate contract.

---

## 6. What is still missing, and whether it matters

| Missing permission | Endpoint | Verdict |
|---|---|---|
| Pull requests: **Read and write** | `POST /pulls/{n}/reviews` | Optional. Would let the gate post review verdicts as review comments instead of only commit statuses. |
| Administration: Read | `GET /branches/main/protection` | **Pointless** — reads are plan-blocked too (§4). |
| Workflows: Read and write | editing `.github/workflows/*` | Needed only to merge Dependabot PRs that bump workflow files (#23/#24/#25/#36 historically). Actions is billing-disabled here, so those PRs are low value. |

---

## 7. Never do this again

The false-green that hid RISK-015 for weeks was a run that reported
`statuses=8` while GitHub received nothing. The invariant every future auth
change must preserve:

> A credential's permissions must be a **superset of that function's needs and a
> subset of its entitlement** — and the failure when it is not must be **loud**.

`ci_bridge.py` now reports `published=N/M` and exits non-zero on a publish
failure. Any auth refactor must keep that. **Prove the effect, not the call.**
