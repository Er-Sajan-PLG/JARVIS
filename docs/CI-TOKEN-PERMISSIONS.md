# JARVIS CI — GitHub token permissions

Authoritative record of what each token on this machine can do and what the local
CI gate actually needs. Every row below was measured with a live API probe, not
read off the GitHub UI. Re-verify with:
`python3 /tmp/jarvis_resolve_service_token.py`

## The split — one token, two jobs, no token that does both

`scripts/ci_bridge.py` resolves a **single** token (`load_token()`) and then uses
that same token for two different operations:

| job | call | permission needed |
|-----|------|-------------------|
| list open PRs | `GET /repos/{o}/{r}/pulls` | **Pull requests: Read** |
| publish the gate result | `POST /repos/{o}/{r}/statuses/{sha}` | **Commit statuses: Read and write** |

On 2026-09-11 the tokens on this box were split exactly along that seam:

| token | stored in | list PRs | publish status |
|-------|-----------|----------|----------------|
| `JARVIS_CI_TOKEN` | `JARVIS/.env` | 403 | **201 OK** |
| `github_pat_hermes` (= `GITHUB_MCP_PAT`) | `JARVIS/.env`, `~/.hermes/.env`, shell | **200 OK** | 403 |
| `n8n_github_token` (= `GH_TOKEN`, = `gh` CLI token) | `JARVIS/.env`, shell, `gh` | **200 OK** | 403 |

So whichever token wins, one half of the job fails — either the run cannot list
PRs at all, or it gates them and every status POST is refused. That is exactly the
`conclusion=success statuses=8` line that was green while GitHub received nothing.

## What the service actually resolves (and why it is the wrong one)

`.ci-bridge.env` is a systemd `EnvironmentFile`, so the bridge gets only
`CI_BRIDGE_*`. `load_token()` therefore falls through to `TOKEN_FILES`, in order:

1. `~/Projects/.env` — does not exist
2. `~/.hermes/.env` — **`GITHUB_MCP_PAT` wins here** ← current behaviour
3. `JARVIS/.env` — never reached; this is where `JARVIS_CI_TOKEN` lives

`ci_bridge.py --check-auth` confirms:
`source: /home/sajan/.hermes/.env:GITHUB_MCP_PAT`

That token can list PRs but cannot publish, which is precisely the failure seen:
the gate ran, and all 8 statuses came back 403.

`TOKEN_VARS` order (`JARVIS_CI_TOKEN` first) only decides *within* a single
source. An **environment variable beats every file**, so putting
`JARVIS_CI_TOKEN` in `.ci-bridge.env` is what actually makes the service use it.

## Required permission set

### For the CI publisher — `JARVIS_CI_TOKEN` (the one that matters)

Repository access: **only** `Er-Sajan-PLG/JARVIS`.

| permission | level | why |
|------------|-------|-----|
| **Contents** | Read | `git fetch` of the PR head and base branch |
| **Pull requests** | **Read** | `GET /pulls` to discover what to gate — **currently missing** |
| **Commit statuses** | **Read and write** | the 8 published gate contexts — already present |
| Metadata | Read | mandatory, granted automatically |

Add **Pull requests: Read** and this token alone can run the whole gate. No other
token is then needed for CI.

### If you would rather use one of the dev tokens instead

`github_pat_hermes` or `n8n_github_token` would each need **Commit statuses:
Read and write** added. They already have Contents: Read and Pull requests: Read.

## Branch protection: this is NOT a token problem (measured 2026-09-13)

This file previously listed `Administration: Read` as the missing permission for
branch protection. That was wrong, and the correction matters because it decides
whether granting a permission can fix anything.

Two **different** 403s come back from the same endpoint, and only one is a token
problem:

| caller | token | 403 body |
|--------|-------|----------|
| `JARVIS_CI_TOKEN` (fine-grained) | `github_pat_11C…` | `Resource not accessible by personal access token` |
| `gh` CLI (classic, `repo` scope = includes administration:write) | `gho_…` | `Upgrade to GitHub Pro or make this repository public to enable this feature.` |

The second caller is **not** short of scope — `repo` covers administration:write,
and `GET /collaborators/Er-Sajan-PLG/permission` returns `"permission": "admin"`
with GraphQL `viewerPermission: ADMIN`, `viewerCanAdminister: true`. It still gets
the *plan* message. Repository **rulesets** are gated identically
(`GET`/`POST /rulesets` → the same upgrade message), so there is no ruleset escape
hatch on a private Free repo.

**Conclusion:** granting the CI token `administration: write` will **not** enable
branch protection. The block is the GitHub plan, as RISK-012 says. Do not spend
time on token scopes for this.

## What granting permission WOULD fix (the real list)

Probed 2026-09-13 with `x-accepted-github-permissions` from GitHub itself. The CI
token currently holds `metadata=read`, `pull_requests=read`, `statuses=write`,
`contents=read`. Missing permissions and what each unblocks:

| missing permission | endpoint that 403s | what it would unblock |
|--------------------|--------------------|------------------------|
| **Contents: Read and write** | `PUT /pulls/{n}/merge` (`contents=write`) | **merging green PRs from the bridge** — see below |
| **Contents: Read and write** | `POST /releases`, `POST /git/refs` (`contents=write`) | creating releases/tag refs over the API (today: via `gh` in `scripts/publish_release.py`) |
| **Pull requests: Read and write** | `POST /pulls/{n}/reviews` (`pull_requests=write`) | posting review verdicts/comments on PRs |
| Administration: Read | `GET /branches/main/protection` (`administration=read`) | *reading* protection config only — pointless while writes are plan-blocked |

`Contents: Read and write` is the one worth granting: it is what turns the local
gate from "publishes a verdict" into "publishes a verdict **and merges it**",
which is the auto-merge behaviour this repo wants and cannot get from GitHub's
own auto-merge feature (`allow_auto_merge: false` and not settable here).

## The stuck Dependabot PRs are a merge-permission symptom

Observed 2026-09-13: PRs **#44–#53 sit OPEN**. They are not failing — they are
simply never merged and nothing merges them:

- `gh pr view 50` → `mergeable: MERGEABLE`, `mergeStateStatus: CLEAN`
- `GET /commits/<head>/status` → `state: pending`, **0 statuses** — never gated
- `.governance/ci_bridge_state.json` lists gated PRs 25/36/51/52/53/57/58/59 but
  not 44–50, so the bridge never picked them up
- `PUT /pulls/50/merge` with the CI token → **403** `contents=write`
- `allow_auto_merge: false` → GitHub-side auto-merge cannot cover the gap

So even a fully green Dependabot PR cannot be merged by the automation today. Fix
= grant **Contents: Read and write**, then have the bridge merge PRs whose gate
conclusion is `success`.

## Stale claims in this file (corrected)

- Token sources: `.ci-bridge.env` is now **first** in `TOKEN_FILES` and the bridge
  resolves it — `ci_bridge.py --check-auth` reports
  `source: /home/sajan/Projects/JARVIS/.ci-bridge.env:JARVIS_CI_TOKEN`, not
  `~/.hermes/.env:GITHUB_MCP_PAT` as the section above claims. The ordering fix
  (RISK-015) landed after that section was written.
- `JARVIS_CI_TOKEN` already has **Pull requests: Read** — `GET /pulls` → 200. The
  "currently missing" note is out of date.

## The fix

1. **GitHub side:** add **Pull requests: Read** to the token stored as
   `JARVIS_CI_TOKEN`. (Contents: Read and Commit statuses: Read and write it
   already has.)
2. **Local side:** put `JARVIS_CI_TOKEN=<that token>` in
   `/home/sajan/Projects/JARVIS/.ci-bridge.env`, so the service reads it before
   any file in `TOKEN_FILES`.
3. `systemctl --user restart jarvis-ci-bridge`

Then `scripts/ci_bridge.py --once --limit 1` should report
`published=8/8` instead of `published=0/8`.

## Better design (not yet implemented)

Resolving one token for two jobs with different scopes is the underlying defect —
it works only while a single token happens to hold both permissions. The robust
shape is two tokens: a read token for listing, and a write token used only for
`POST /statuses`. That keeps the publishing credential narrowly scoped and stops
a change to either permission set from silently disabling CI. Tracked under
RISK-015.
