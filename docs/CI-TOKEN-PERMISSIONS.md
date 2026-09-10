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

### Not needed for CI, but relevant elsewhere

| permission | token | why |
|------------|-------|-----|
| Workflows: Read and write | any token used via the API | unblocks PRs #23/#24/#25/#36, which edit `.github/workflows/*` |
| Administration: Read | — | branch protection returns 403 on this private free-tier repo; accepted as RISK-012 |
| Actions / Contents: Read and write | `n8n_github_token` | `JARVIS-Cleanup` deletes branches and workflow runs |

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
