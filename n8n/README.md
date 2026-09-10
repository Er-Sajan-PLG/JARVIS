# n8n — JARVIS Local Automation

> Canonical beginner guide: [`docs/N8N-SETUP.md`](../docs/N8N-SETUP.md).
> This file is the short technical reference for the `n8n/` directory.

## Why n8n (not GitHub Actions)

GitHub Actions on a **private** repository is paid. n8n runs locally, for free, so it
takes over the job of *scheduling and reporting* JARVIS checks. The actual checking
logic stays in the repo's own scripts — n8n only orchestrates and reports.

```
n8n (orchestration, :5678)  →  CI bridge (execution, :8770)  →  scripts/ci_bridge.py
```

## Verified state (2026-09-10)

- n8n **v2.34.6**, npm-global binary at `~/.local/bin/n8n`, data in `~/.n8n/database.sqlite`.
- `jarvis-n8n.service` (systemd **user** service, **enabled**, binds `127.0.0.1:5678`).
- `jarvis-ci-bridge.service` (systemd **user** service, **enabled**, binds `127.0.0.1:8770`).
- `loginctl` linger = `yes` → both start on login/reboot.
- `JARVIS-CI-Local` **executes end-to-end** (verified: status `success`, ~100 s, real gate on a real PR).

## Workflows

| File | n8n name | Graph | Runnable now? |
|---|---|---|---|
| `workflows/JARVIS-Local-CI.json` | JARVIS-CI-Local | Manual/Schedule → Config → HTTP POST to bridge → Summarize | ✅ yes |
| `workflows/JARVIS-Cleanup.json` | JARVIS-Cleanup | Schedule → git branches → PR list → branch-list → per-branch loop (HTTP GitHub API) | ⚠️ GitHub cred wired; not yet executed |
| `workflows/JARVIS-HITL.json` | JARVIS-HITL | Webhook → normalize → decision → Slack/Telegram → callback | ❌ not yet runnable (see Honest gaps) |

Each workflow JSON **must have a unique top-level `id`** — collisions cause silent
overwrites on import. Ids in use:

- JARVIS-CI-Local → `6631c9dc-56d2-4af0-93a7-e1da475244d2`
- JARVIS-Cleanup → `7e1d0b2c-9a44-4f6e-b3d1-2c8a5f0e4b91`
- JARVIS-HITL → `2b6f8a41-5c07-4d9e-8f31-a7c4e2b60d55`

## Credentials (in `~/.n8n/database.sqlite`, encrypted)

| Name | Type | Source | Status |
|---|---|---|---|
| `github-api-auth` | httpHeaderAuth | `n8n_github_token` (`JARVIS/.env`) | ✅ |
| `ci-bridge-auth` | httpHeaderAuth | `CI_BRIDGE_TOKEN` (`.ci-bridge.env`) | ✅ |
| `telegram-credentials` | telegramApi | `TELEGRAM_API_KEYS` (`JARVIS/.env`) → `naya_jarvis_bot` | ✅ |
| `slack-credentials` | slackApi | `SLACK_BOT_TOKEN` (`JARVIS/.env`) → team `STEM`, bot `learninghub` | ✅ |
| `jarvis-api-auth` | httpHeaderAuth | `JARVIS_API_KEY` | ❌ missing |

## Commands

```bash
# status / control
systemctl --user status  jarvis-n8n.service jarvis-ci-bridge.service
systemctl --user restart jarvis-n8n.service

# import a workflow from the repo (unique id required!)
cd ~/Projects/JARVIS
n8n import:workflow --input=n8n/workflows/JARVIS-Local-CI.json

# import a credential
n8n import:credentials --input=/path/to/cred.json

# the real CI script, directly (no n8n)
.venv/bin/python scripts/ci_bridge.py --once --limit 1 --dry-run
.venv/bin/python scripts/ci_bridge.py --list-prs
.venv/bin/python scripts/ci_bridge.py --check-auth
```

## Architecture decisions (and why)

1. **n8n v2 removed `n8n-nodes-base.executeCommand`.** So "run a local script" is done
   via `scripts/ci_bridge_server.py` — a tiny, auditable, stdlib-only HTTP wrapper
   bound to localhost, token-protected, executing only a whitelisted flag set of
   `ci_bridge.py`. n8n reaches it with the built-in **HTTP Request** node.
2. **`fetch_pr_head` now fetches over HTTPS with the fine-grained PAT** (inline git
   credential helper, token passed via child env — never in argv). Previously it used
   the SSH remote, which failed headlessly under systemd (no `SSH_AUTH_SOCK`). This is
   what makes the gate work under n8n/service, not just in an interactive shell.

## Honest gaps

- `JARVIS-Cleanup` and `JARVIS-HITL` have **not** been executed end-to-end.
  `JARVIS-HITL` in particular is a **labelled scaffold**, not a working automation.
  All three tokens are now wired (`github-api-auth`, `telegram-credentials`,
  `slack-credentials`), but four blockers remain outside n8n:
  1. `/api/v1/hitl/approve` **does not exist** in JARVIS (`app/adapters/http/router.py`
     exposes only `/api/v1/health` and `/api/v1/chat/completions`).
  2. No `JARVIS_API_KEY` is set, so `jarvis-api-auth` cannot be created.
  3. ~~The Slack node needs a real channel **ID** (and the bot invited to it).~~
     **Done** — channel `C0C0UPLGY12` is set on the node's `channelId` locator and the
     bot's ability to post there was verified with a self-deleting probe.
  4. The Telegram node needs a chat **ID**; `getUpdates` returns HTTP 409 (another
     consumer is polling the bot).
  Only the Telegram node's chat field remains to be filled (`REPLACE_WITH_TELEGRAM_CHAT_ID`).
  We also fixed an inherited bug: the nodes referenced `$credentials.slackChannelId` /
  `$credentials.telegramChatId` / `$credentials.jarvisApiUrl` — fields that do not
  exist on those n8n credential types (they resolved empty and failed silently).
- `JARVIS-Release` / `JARVIS-Incident` (Sprint-4 contract targets) do not exist.
- The original three workflow JSONs were **contract artifacts**, not runnable
  automations (they used the removed `executeCommand` node and a stale `--poll-once`
  flag). `JARVIS-CI-Local` was rebuilt; the others were repaired where possible.
