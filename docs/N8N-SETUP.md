# n8n Local Setup for JARVIS — Beginner Guide

**Status:** working and verified end-to-end (2026-09-10).
**Audience:** you, if you have never used n8n before. Every command here is copy-paste safe.

---

## 1. What is n8n, in one paragraph?

n8n ("n-eight-n") is a **workflow automation tool**. You build little flowcharts on a
web page: a **trigger** (a timer, a webhook, a manual button) starts the flow, then a
chain of **nodes** does something (call an API, run a check, send a Telegram message).

Think of it as "IFTTT / Zapier, but it runs on *your* machine and is free."

**Why we use it here:** GitHub Actions on a **private** repo costs money. n8n runs
locally for free, so it replaces GitHub Actions as the thing that *schedules and
reports* JARVIS checks.

---

## 2. The big picture

```
   n8n (the brain)                    CI bridge (the hands)              GitHub
   ───────────────                    ────────────────────              ──────
   web UI at :5678
        │
        │  1. schedule fires / you click "Execute"
        ▼
   HTTP Request node  ────POST────▶  ci_bridge_server.py :8770
                                          │
                                          │  2. runs the real script
                                          ▼
                                    scripts/ci_bridge.py  ──▶  gate PRs, report status
                                          │
        ◀─────── 3. JSON result ──────────┘
```

**Key idea:** n8n does **not** run shell commands itself (the old "Execute Command"
node was removed in n8n v2). Instead, n8n asks the tiny **CI bridge** to run the
script, and gets JSON back. The bridge is the only thing that touches the shell.

---

## 3. What is installed, and where

| Thing | Location | Notes |
|---|---|---|
| n8n itself | `~/.local/bin/n8n` (v2.34.6, npm global) | Node.js app |
| n8n data (workflows, creds) | `~/.n8n/database.sqlite` | a SQLite file — back this up |
| n8n web UI | http://localhost:5678 | open in browser |
| CI bridge script | `~/Projects/JARVIS/scripts/ci_bridge_server.py` | stdlib-only Python |
| Real CI script | `~/Projects/JARVIS/scripts/ci_bridge.py` | does the GitHub work |
| Bridge secret | `~/Projects/JARVIS/.ci-bridge.env` | git-ignored, chmod 600 |

Both run as **systemd user services**, so they **auto-start on login/reboot**:

- `jarvis-n8n.service` → n8n on `127.0.0.1:5678`
- `jarvis-ci-bridge.service` → bridge on `127.0.0.1:8770`

---

## 4. Day-to-day commands (copy-paste)

```bash
# Are they running?
systemctl --user status jarvis-n8n.service jarvis-ci-bridge.service

# Start / stop / restart
systemctl --user start   jarvis-n8n.service
systemctl --user stop    jarvis-n8n.service
systemctl --user restart jarvis-n8n.service

# Same for the bridge
systemctl --user restart jarvis-ci-bridge.service

# Read the logs (Ctrl+C to exit)
journalctl --user -u jarvis-n8n.service -f
journalctl --user -u jarvis-ci-bridge.service -f

# Quick "is it alive?" checks
curl -s http://127.0.0.1:5678          # n8n UI HTML
curl -s http://127.0.0.1:8770/health   # {"status":"ok", ...}
```

The bridge's health endpoint tells you if auth is on:

```json
{"status":"ok","service":"jarvis-ci-bridge","repo":"/home/sajan/Projects/JARVIS","authRequired":true}
```

---

## 5. Opening n8n for the first time

1. Make sure the service is running (`systemctl --user start jarvis-n8n.service`).
2. Open **http://localhost:5678** in your browser.
3. You should land on the workflow list. Your owner account is already created.

You will see three workflows:

| Workflow | What it does | Ready to run? |
|---|---|---|
| **JARVIS-CI-Local** | Schedules the local CI gate (replaces GitHub Actions) | ✅ **Yes** |
| **JARVIS-Cleanup** | Housekeeping via GitHub API | ⚠️ GitHub cred wired; review before use |
| **JARVIS-HITL** | Human-in-the-loop approvals (Telegram/Slack) | ❌ Not yet runnable — see §7.1 |

---

## 6. Running a workflow (the beginner way)

1. Click **JARVIS-CI-Local**.
2. You will see 5 boxes: `Manual Trigger` / `Schedule every 6h` → `Config` →
   `Run Local CI (bridge)` → `Summarize Result`.
3. Click the **Execute Workflow** button (bottom-centre, the ▶ play icon).
4. Watch the boxes light up green one by one. The whole thing takes ~1–2 minutes
   (it is running a real test gate on a real pull request).
5. Click any box to inspect its input/output. Click **Summarize Result** to see the
   final verdict.

**The `Config` box is your control panel.** Double-click it and edit:

```js
const limit   = 1;      // how many PRs to gate per run (1 = fast; raise for full runs)
const dryRun  = true;   // true = analyse only, don't post statuses to GitHub
return [{ json: { limit, dryRun, body: { limit, dryRun } } }];
```

- `dryRun: true` → safe, changes nothing on GitHub. **Start here.**
- `dryRun: false` → actually posts commit statuses (this is the real GitHub-Actions
  replacement).
- `limit: 1` → ~1–2 min. `limit: 0` (or remove) → all open PRs (~18 min for 10 PRs).

### Making it run automatically

The workflow ships **inactive** on purpose. When you are happy with it:

1. Open the workflow.
2. Flip the **Active** toggle (top-right).
3. It now fires every 6 hours. (Edit the `Schedule every 6h` box to change the timing.)

---

## 7. Credentials (what n8n uses to log in to other services)

Manage them at **http://localhost:5678 → Credentials**.

| Credential | Type | Status |
|---|---|---|
| `github-api-auth` | Header Auth (`Authorization: Bearer …`) | ✅ created from your n8n PAT |
| `ci-bridge-auth` | Header Auth (`X-Bridge-Token: …`) | ✅ created (bridge secret) |
| `telegram-credentials` | Telegram | ✅ created from your bot token (`naya_jarvis_bot`) |
| `slack-credentials` | Slack | ✅ created from your bot token (team `STEM`, bot `learninghub`) |
| `jarvis-api-auth` | Header Auth | ❌ missing — add `JARVIS_API_KEY` for HITL callbacks |

To add a missing one: **Credentials → Add credential → pick the type → paste the
token → Save.** The workflow will pick it up automatically (the names must match
exactly).

### 7.1 Why JARVIS-HITL does not run yet (honest gap list)

`JARVIS-HITL` was a Sprint-4 **contract artifact**: it describes the intended
approval flow but was never executable. The tokens are now wired, but four concrete
blockers remain — all outside n8n:

1. **No callback endpoint.** The two `… Callback to JARVIS` nodes POST to
   `/api/v1/hitl/approve`, which **does not exist**. `app/adapters/http/router.py`
   only exposes `/api/v1/health` and `/api/v1/chat/completions`. Something must
   implement that route before the loop can close.
2. **No `JARVIS_API_KEY`.** `validate_api_key()` returns `"development"` and skips
   auth when the var is unset, so there is no key to put in `jarvis-api-auth` yet.
3. **Slack channel ID unknown.** The `Send to Slack` node needs a real channel ID
   (e.g. `C0XXXXXXXXX`), and the `learninghub` bot must be **invited** to that
   channel. Its token lacks `channels:read`, so it cannot list channels itself.
   Set the node's `channel` field (currently `REPLACE_WITH_SLACK_CHANNEL_ID`).
4. **Telegram chat ID unknown.** The `Send to Telegram` node needs a chat ID
   (`REPLACE_WITH_TELEGRAM_CHAT_ID`). `getUpdates` currently returns HTTP 409
   (another consumer / webhook is polling this bot), so the ID cannot be discovered
   from the terminal.

We also fixed an inherited bug: the notification nodes referenced
`{{ $credentials.slackChannelId }}` / `{{ $credentials.telegramChatId }}` /
`{{ $credentials.jarvisApiUrl }}` — fields that **do not exist** on those n8n
credential types, so they resolved to empty strings and failed silently. They now
read from explicit node fields / a literal URL.

**Bottom line:** the CI path is real and verified; HITL is a labelled scaffold.

---

## 8. Importing / re-importing a workflow from the repo

The repo is the source of truth for workflow JSON. After editing a file in
`n8n/workflows/`, load it back into n8n:

```bash
cd ~/Projects/JARVIS
n8n import:workflow --input=n8n/workflows/JARVIS-Local-CI.json
```

> ⚠️ **Gotcha:** every workflow JSON needs a **unique `id`**. If two files share an
> `id`, the second import silently **overwrites** the first. Each file here has its
> own UUID.

---

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| Browser can't reach :5678 | `systemctl --user restart jarvis-n8n.service`, then `journalctl --user -u jarvis-n8n.service -n 50` |
| Workflow errors on the bridge node with `401` | The `ci-bridge-auth` credential token doesn't match `.ci-bridge.env`. Recreate it. |
| Workflow errors with `fetch-failed` | git auth. The script fetches over HTTPS with your PAT; confirm `GITHUB_MCP_PAT` (or `n8n_github_token`) is present and unexpired. |
| `EADDRINUSE` / port already in use | Something else is on 5678/8770. `ss -ltnp \| grep -E '5678\|8770'` |
| n8n won't start at all | `cd ~/Projects/JARVIS && n8n start` in a terminal to see the error live. |

> **Note:** do **not** run `n8n execute --id …` from the CLI while the service is
> running — they fight over the internal task-broker port. Stop the service first.

---

## 10. Security notes

- The bridge binds **only to `127.0.0.1`** (this machine), never the network.
- It requires a shared token in the `X-Bridge-Token` header (`401` otherwise).
- The token lives in `.ci-bridge.env` (git-ignored, mode 600).
- The bridge does **not** accept arbitrary commands — only the fixed
  `scripts/ci_bridge.py` with a whitelisted set of flags.
- n8n's own data lives in `~/.n8n/database.sqlite`; treat it as sensitive (it holds
  encrypted credentials).

---

## 11. Why the repo's old workflows didn't run (honest history)

The three JSON files were originally written as **Sprint-4 contract artifacts** —
i.e. documents asserting "these workflows should exist", written *before* anyone ran
them. Two things were wrong:

1. They used `n8n-nodes-base.executeCommand`, a node **removed in n8n v2**. It would
   never have run.
2. They referenced credentials that did not exist, and one file used a stale
   command flag (`--poll-once`) that the real script doesn't accept.

`JARVIS-CI-Local` has now been rebuilt around the HTTP bridge and **actually
executes**. The other two have been repaired where possible and are labelled honestly
above.
