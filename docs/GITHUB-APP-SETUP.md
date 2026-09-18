# GitHub App setup (ADR-012 migration)

**Status**: ACTIVE
**Type**: runbook
**Source**: `scripts/ci_bridge.py` at HEAD
**Last Updated**: 2026-09-13
**Reviewed**: 2026-09-14

The CI gate currently publishes with a fine-grained PAT (`JARVIS_CI_TOKEN`). That
works — verified: `published=9/9`, and GitHub read-back returns
`state=success, total_count=9`. This document is the next step: moving each
function onto its own **GitHub App**, so the credential is short-lived, not tied
to a person, and attributed to the App in the audit log.

The code side is **already done and tested**. Creating the App is a GitHub
website action and can only be done by the account owner — it is the one step
below that I cannot perform.

---

## Why bother (the two rows that decide it)

| | fine-grained PAT | App installation token |
|---|---|---|
| lifetime | up to 1 year | **1 hour**, automatic |
| tied to a person | **yes** — breaks when they lose repo access | no |
| audit trail | "the human did it" | **the App** did it |
| scale ceiling | **50 per user** | none |
| revocation | revoke the PAT | uninstall the App |

A leaked PAT is a standing liability for up to a year. A leaked installation
token is dead in an hour.

---

## Step 1 — create the App (GitHub UI, ~2 minutes)

1. GitHub → click your avatar → **Settings**
2. Left sidebar, bottom → **Developer settings**
3. **GitHub Apps** → **New GitHub App**

Fill in:

| field | value |
|---|---|
| GitHub App name | `jarvis-ci` (must be globally unique — add a suffix if taken) |
| Homepage URL | `https://github.com/Er-Sajan-PLG/JARVIS` |
| Webhook → **Active** | **untick this.** No webhooks are needed. |

**Repository permissions** — grant exactly these three, nothing else:

| permission | level | why |
|---|---|---|
| **Contents** | Read and write | `git fetch` of the PR head and base branch (read) + merging a green PR via `PUT /pulls/{n}/merge` (write) |
| **Pull requests** | Read | `GET /pulls` to discover what to gate |
| **Commit statuses** | Read and write | publish the 9 gate contexts |
| Metadata | Read | mandatory, granted automatically |

Leave every other permission at **No access**. That is the point of the exercise.

At the bottom: **Where can this GitHub App be installed?** → *Only on this
account*. Then **Create GitHub App**.

## Step 2 — collect the three values

**App ID** — shown at the top of the App's page after creation. A number.

**Private key** — scroll to the bottom → **Generate a private key**. A `.pem`
file downloads. Move it somewhere outside the repository and lock it down:

```
mkdir -p ~/.jarvis
mv ~/Downloads/jarvis-ci.*.private-key.pem ~/.jarvis/jarvis-ci-app.pem
chmod 600 ~/.jarvis/jarvis-ci-app.pem
```

The private key is now the most valuable secret on this machine. It must never
be committed, printed, or moved into the repo.

**Installation ID** — left sidebar of the App page → **Install App** → choose
`Er-Sajan-PLG` → *Only select repositories* → `JARVIS` → **Install**. After
installing, the browser URL is
`https://github.com/settings/installations/<NUMBER>` — that number is the
installation ID.

You can also let the tool discover it instead:

```
cd ~/Projects/JARVIS
JARVIS_APP_ID=<id> JARVIS_APP_PRIVATE_KEY_PATH=~/.jarvis/jarvis-ci-app.pem \
  .venv/bin/python scripts/github_app_token.py --installation-id
```

## Step 3 — wire it into the bridge

Add these three lines to `/home/sajan/Projects/JARVIS/.ci-bridge.env` (the file
already exists; it currently holds `CI_BRIDGE_TOKEN`, `CI_BRIDGE_PORT`,
`CI_BRIDGE_HOST`, `JARVIS_CI_TOKEN` — leave all four alone):

```
JARVIS_APP_ID=<app id>
JARVIS_APP_PRIVATE_KEY_PATH=/home/sajan/.jarvis/jarvis-ci-app.pem
JARVIS_APP_INSTALLATION_ID=<installation id>
```

Then:

```
systemctl --user restart jarvis-ci-bridge
cd ~/Projects/JARVIS && .venv/bin/python scripts/ci_bridge.py --check-auth
```

Expected output — note the source line:

```
AUTH OK
  source : github-app:<app id> (installation <installation id>)
  login  : Er-Sajan-PLG
  repo   : Er-Sajan-PLG/JARVIS (private=True, push=True)
```

`source : github-app:...` means the App token won and the PAT is now unused. If
it still says `env:JARVIS_CI_TOKEN`, the App is not configured correctly.

## Step 4 — verify the effect, not the call

```
cd ~/Projects/JARVIS
TOKEN=$(grep -m1 '^CI_BRIDGE_TOKEN=' .ci-bridge.env | cut -d= -f2-)
curl -s --max-time 880 -X POST http://127.0.0.1:8770/run \
  -H "Content-Type: application/json" -H "X-Bridge-Token: $TOKEN" \
  -d '{"limit":1,"dryRun":false}' | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('ok:',d['ok'],'exit:',d['exitCode'],'dur:',d['durationSec'],'s')
print([l for l in d['stdout'].splitlines() if 'published=' in l][-1])
"
```

Look for `published=9/9`. A green gate that published nothing is not a pass.

---

## What changes once the App is live

- The token expires every hour and is re-minted automatically; a cache in
  `~/.jarvis/app-token-cache.json` (mode 0600) keeps it to roughly one mint per
  hour so a 30-minute schedule does not mint twice per run.
- Verify the cache (proves reuse, not just minting):

  ```
  ls -l ~/.jarvis/app-token-cache.json   # -rw------- (0600, owner-only)
  cd ~/Projects/JARVIS && .venv/bin/python scripts/github_app_token.py --check
  # a second run within the hour reports source github-app:<id> (cached)
  ```
- `JARVIS_CI_TOKEN` in `.ci-bridge.env` becomes a **fallback**. Once the App is
  proven, it can be removed — which is the whole point: one fewer long-lived
  secret on disk.
- If the App is configured but broken, `load_token()` **raises** rather than
  quietly falling back to the PAT. A silent fallback is how a permission
  regression hides for weeks (that was RISK-015).

## Bonus, for later

A PAT **cannot** write check-runs (`POST /check-runs` → 403 "You must
authenticate via a GitHub App"). An App installation token **can**. So once the
App is in place, the gate could publish check-runs instead of commit statuses —
richer output, and the thing branch protection actually wants. That is a
separate change; noted, not done.

## Files

| file | role |
|---|---|
| `scripts/github_app_token.py` | mints + caches the installation token (RS256 JWT → token exchange) |
| `tests/unit/test_github_app_token.py` | 17 tests: JWT shape, signature verification, key-type guard, cache expiry, migration safety |
| `docs/adr/ADR-012-github-auth-identity-per-function.md` | the decision and the function-to-identity map |
| `docs/CI-TOKEN-PERMISSIONS.md` | current PAT permission matrix |
