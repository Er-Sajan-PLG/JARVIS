# n8n Handover — How This Works and How to Take Over

**Status**: ACTIVE
**Type**: guide
**Last Updated**: 2026-09-13
**Reviewed**: 2026-09-14

**Audience**: the human owner of this repo. Written after an autonomous session that built
the CI gate and the HITL loop. **New working agreement**: you edit workflows in the n8n
UI; the agent reads your edits back out of the database, diffs them, and commits them.

---

## 1. What is actually running on this machine

| Thing | What it is | Where |
|---|---|---|
| `jarvis-n8n.service` | The n8n editor + scheduler | http://localhost:5678 (systemd user unit) |
| `jarvis-ci-bridge.service` | Small HTTP wrapper around `scripts/ci_bridge.py` so n8n can trigger CI | http://127.0.0.1:8770 (`/health`) |
| `python -m app.main` | JARVIS itself (the product) | http://127.0.0.1:8000 |

Check them:
```bash
systemctl --user status jarvis-n8n.service jarvis-ci-bridge.service
curl -s http://127.0.0.1:8770/health
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/v1/health
```

## 2. Why n8n looks "simple" — and why that is deliberate

n8n is the **conductor, not the orchestra**. It has exactly three jobs:

| Workflow | Trigger | What it does |
|---|---|---|
| `JARVIS-CI-Local` | every 30 min | POSTs to the bridge → the bridge runs the <!--fact:gate_count-->26<!--/fact-->-check gate and publishes GitHub statuses |
| `JARVIS-HITL` | every 1 min (poll) + a webhook | Finds JARVIS approvals waiting on a human, tells you on Slack, accepts your approve/deny |
| `JARVIS-Cleanup` | schedule | Housekeeping |

All the actual checking lives in `scripts/ci_bridge.py` and `scripts/ci_gate.py` — versioned,
testable, reviewable Python. Keep it that way: if logic ends up inside an n8n node, it stops
being testable and stops being in git.

## 3. How to edit a workflow (your new workflow)

1. Open http://localhost:5678 → left sidebar → **Overview** → click a workflow name.
2. Click a node on the canvas to open its panel on the right. Edit the fields.
   - **HTTP Request** nodes: the interesting fields are *Method*, *URL*, *Send Body* →
     *Body Content Type* = JSON, and the **Authentication** dropdown (keep
     `Generic Credential Type` → `Header Auth`).
   - For JSON bodies you want n8n to fill in values, the field must **start with `=`**.
     That is the single biggest gotcha here — see §6.
3. Click **Save** (top right). In n8n 2.x a schedule-triggered workflow only *runs* the
   version that is **published** — so after saving, make sure the workflow is still
   **Active** (the toggle in the top bar). If a change seems to have no effect, toggle
   Active off and on again, or restart the service:
   `systemctl --user restart jarvis-n8n.service`
4. Verify with the **Executions** tab (left sidebar → Executions): each run lists its
   status and per-node output. Green here means the node actually ran.

## 4. How the agent reads your edits back

After you save in the UI, the agent exports from the database and commits:

```bash
N8N_USER_FOLDER=/home/sajan n8n export:workflow \
  --id=e0f3e292-55ad-488d-927f-1417655fcabd \
  --output=n8n/workflows/JARVIS-HITL.json --pretty
```

Workflow IDs:
- `JARVIS-HITL` → `e0f3e292-55ad-488d-927f-1417655fcabd`
- `JARVIS-CI-Local` → `6631c9dc-56d2-4af0-93a7-e1da475244d2`
- `JARVIS-Cleanup` → `4b435cd8-00dc-436c-8308-ee80e7bcab8e`

**Golden rule**: the UI is where you edit; the JSON file in `n8n/workflows/` is what gets
committed and reviewed. Don't hand-edit both.

## 5. What the agent changed in n8n (so nothing is a mystery)

Five real bugs were found and fixed in `JARVIS-HITL` — all of them silent failures, which is
why the workflow looked "fine" while doing nothing:

1. **HTTP nodes were the legacy v1 type**, which ignores `genericCredentialType`. No
   Authorization header was ever sent → every poll died with `401 Unauthorized`.
   Fixed: all HTTP nodes are now **typeVersion 4.2**.
2. **Literal templates were sent to Slack** — the body was a plain JSON string, so Slack
   received the text `{{ $json.planId }}` instead of the value. Fixed: bodies are now
   expressions (they start with `=`).
3. **Legacy `Function` nodes** crash with a TypeError (no `$json`/`items` the way they were
   written). Fixed: converted to **Code** nodes.
4. **The webhook registered at a mangled URL** (`/webhook/<wf-id>/approval callback/...`)
   because the node had no `webhookId`. Fixed → `/webhook/hitl/callback`.
5. **The dedupe never stuck**, so every tick re-notified every approval (6 messages in 2
   minutes). n8n's workflow static data does not persist in this build. Fixed: the marker
   lives in JARVIS (`notified_at`), see §7.

Credentials in n8n (all `httpHeaderAuth` unless noted):
`ci-bridge-auth`, `github-api-auth`, `jarvis-api-auth`, `slack-bot-auth`,
`slack-credentials` (slackApi), `telegram-credentials` (telegramApi).

> Never paste credentials into a chat or a file the agent prints. They are read from
> `/home/sajan/Projects/JARVIS/.env` and `.ci-bridge.env`.

## 6. Golden rule: the `=` prefix

n8n evaluates a field **only** if its value starts with `=`. This bit us three times.

```
jsonBody: {"plan_id": "={{ $json.planId }}"}          ← WRONG: literal text is sent
jsonBody: ={{ JSON.stringify({plan_id: $json.planId}) }}  ← RIGHT
```

Related: a **Webhook** node wraps the payload as `{ headers, params, query, body }`, so the
posted JSON is at `items[0].json.body`.

## 7. The HITL contract (what JARVIS expects)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/hitl/pending` | GET | approvals waiting on a human; includes `notified_at` |
| `/api/v1/hitl/notified` | POST | `{plan_id, step_id}` — stamp "we told the human" (idempotent) |
| `/api/v1/hitl/approve` | POST | `{plan_id, step_id, decision: approve\|deny, approver, reason}` |
| `/api/v1/chat/completions` | POST | the pipeline; a destructive request comes back paused |

All require `Authorization: Bearer $JARVIS_API_KEY`.

Try the whole loop by hand (the fastest way to see it work):
```bash
cd ~/Projects/JARVIS && set -a; . ./.env; set +a

# 1. ask JARVIS to do something destructive — it pauses instead of acting
curl -s -X POST http://127.0.0.1:8000/api/v1/chat/completions \
  -H "Authorization: Bearer $JARVIS_API_KEY" -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"create directory /tmp/demo-hitl"}]}' | python3 -m json.tool

# 2. see it waiting
curl -s -H "Authorization: Bearer $JARVIS_API_KEY" http://127.0.0.1:8000/api/v1/hitl/pending | python3 -m json.tool

# 3. approve it (copy plan_id / step_id from step 2)
curl -s -X POST http://127.0.0.1:8000/api/v1/hitl/approve \
  -H "Authorization: Bearer $JARVIS_API_KEY" -H 'Content-Type: application/json' \
  -d '{"plan_id":"plan-xxxx","step_id":"plan-xxxx-s1","decision":"approve","approver":"me"}'
ls -d /tmp/demo-hitl   # the directory now exists — it only ran after approval
```

Within ~1 minute the n8n poll will also have posted a Slack message about it.

## 8. Still needs YOU (nothing the agent can do)

1. **Slack Approve/Deny buttons.** The Slack app needs an **Interactivity Request URL**
   pointing at `http://<your-host>:5678/webhook/hitl/callback`. Until then approval works by
   calling the webhook/API, not by clicking the buttons. (Also note: the callback currently
   answers `{"myField":"value"}` — cosmetic, worth tidying when you wire the buttons.)
2. **Telegram.** The node is **disabled** on purpose: there is no chat ID yet and
   `getUpdates` returns 409 (another poller holds the connection). Send the bot a message
   and give the agent the chat ID, then enable the node.
3. **Dependabot PRs.** *Snapshot 2026-09-10:* four PRs (#23, #24, #25, #36)
   bumped `.github/workflows/*` and were refused by GitHub because the
   fine-grained PAT lacked **Workflows: write**; **#40** had a real merge
   conflict. *Current state:* the open Dependabot PRs touch only
   `requirements.txt`, so the Workflows-permission refusal no longer applies
   — merge them normally after the gate is green, or close them if superseded.
   If a future Dependabot PR touches `.github/workflows/` again, the same
   refusal will return (the CI token must not hold Workflows: write — see
   `docs/CI-TOKEN-PERMISSIONS.md`).
4. **`tests/sprint4/` stubs.** *Snapshot 2026-09-10:* RED TDD stubs for
   Sprint 4 (incident/release workflows), deliberately untracked — committing
   them turned the gate red. *Current state:* the directory holds no test
   sources (only `__pycache__`) and is still untracked. Decide whether
   Sprint 4 is next before writing new tests there.

## 9. Where the decisions are written down

- `docs/DECISIONS-AUTONOMOUS-2026-09-10.md` — every call the agent made while you were away:
  why, what else was on the table, how it was verified.
- `docs/adr/ADR-011-tool-wiring-and-hitl-gate.md` — the architecture decision behind tool
  wiring, destructive-intent routing, and polling vs push.
- `docs/ACCEPTED_RISKS.md` — RISK-014 flipped from *unreachable* to *Resolved (verified
  live)*. Nothing was marked green without a live test behind it.
