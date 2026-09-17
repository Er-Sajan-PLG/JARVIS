# Mobile Access — Using JARVIS from a Phone

**Status**: ACTIVE
**Type**: runbook
**Last Updated**: 2026-09-17
**Source**: app/main.py, frontend/assets/service-worker.js, frontend/assets/manifest.json

> Drift trap for this type: The command or endpoint changes and the runbook keeps instructing the old one, so following it fails at the worst moment.

---

## What this covers

JARVIS is served as an installable web app (PWA). A phone on the same private
network opens a URL, adds JARVIS to its home screen, and gets a full-screen app
with push notifications — no app store, no separate mobile build.

Two facts decide whether this works:

1. **The console frontend uses relative API paths** (`/api/...`), so it needs no
   rebuild to be reached from another device. The only variable is the origin the
   phone opens.
2. **A service worker is only honoured at the scope it controls.** JARVIS serves
   it from the origin root with `Service-Worker-Allowed: /` so it can control
   navigations. Without that header the browser caps the scope at the script's
   own directory and install/push silently fail.

---

## Prerequisites

| Requirement | Why | Check |
|---|---|---|
| Phone and host on the same network | The server is reached directly, not via a third party | Both on the same Wi-Fi, or both on the tailnet |
| `JARVIS_API_KEY` set in `.env` | Binding a non-loopback interface exposes JARVIS to every device that can route to it | `grep '^JARVIS_API_KEY=.' .env` |
| Python venv present | The server runs from `.venv` | `ls .venv/bin/python` |
| Host reachable at a stable address | The phone needs one URL to bookmark and install from | See *Choose an address* below |

**Choose an address.** Two supported options:

- **LAN** — simplest, no extra software, works only on the same Wi-Fi:
  `http://<host-lan-ip>:8000`, e.g. `http://192.168.1.81:8000`.
- **Private tunnel (Tailscale)** — works from any network, encrypted, still not
  public: `http://<host-tailnet-name>:8000`, e.g. `http://sajan-pc:8000`.
  Install Tailscale on the host and the phone, sign both into the same tailnet,
  then use the MagicDNS name.

> **Why not bind `0.0.0.0` with no key.** If `JARVIS_API_KEY` is unset,
> `app/adapters/security.py` deliberately allows **every** request. On a shared
> Wi-Fi network that hands full control of JARVIS to anyone on it. The server logs
> a warning when it starts in this state, but it does not refuse to start.

---

## What the API key actually protects

There are two HTTP surfaces, and they are gated the same way — by
`JARVIS_API_KEY` — but they are served by different routers:

| Surface | Routes | Examples | Key required? |
|---|---|---|---|
| Console API | `/api/*` | `/api/chat`, `/api/models`, `/api/conversations`, `/api/settings/*`, `/api/upload` | **Yes** |
| REST API | `/api/v1/*` | `/api/v1/chat/completions`, `/api/v1/health`, `/api/v1/hitl/*` | **Yes** |
| Installable app | `/`, `/manifest.json`, `/service-worker.js`, `/offline.html`, `/icon-*.png`, `/badge.png`, `/static/*` | the shell, its assets | **No — deliberately** |

The app surface must stay public: a browser fetches the manifest, the service
worker and the icons *before* any credential exists, and `cache.addAll` is
atomic. Gating them would make the app uninstallable and the service worker
unable to register — which also stops push notifications from ever working.

**The console sends the key for you** once it is entered in
*Settings → Access*. It is stored per-origin in `localStorage`, so it stays on
the device. A device that has never been set up shows
"JARVIS requires an API key" rather than a blank console.

> **History worth knowing.** Before this runbook existed, only `/api/upload`
> carried the auth dependency. Every other console route — chat, the provider
> catalogue, conversations, and `/api/settings/api-keys` — answered anonymous
> requests even with a key configured. Binding to a non-loopback interface
> without first fixing that would have handed JARVIS to the network. The gate is
> now applied once, at the router, and `tests/contract/test_console_auth.py`
> pins it.

---

## Procedure

### 1. Set the API key (once)

```bash
cd /home/sajan/Projects/JARVIS
# Generate a key and write it into .env
printf 'JARVIS_API_KEY=%s\n' "$(openssl rand -hex 32)" >> .env
grep '^JARVIS_API_KEY=' .env | sed 's/=.*/=<set>/'
```

The console stores this key in the browser, so the phone only needs it entered
once.

### 2. Allow the phone's origin (Tailscale only)

The server allowlists its own origin automatically for LAN use. For a tunnel
hostname, name the exact URL the phone will open:

```bash
# In .env — the scheme + host + port the phone types, no trailing slash
JARVIS_PUBLIC_ORIGIN=http://sajan-pc:8000
```

### 3. Start the server bound for the network

`app/main.py` has a real entry point and binds `0.0.0.0` by default so other
devices can reach it:

```bash
cd /home/sajan/Projects/JARVIS
.venv/bin/python -m app.main
```

Override the bind when needed:

```bash
JARVIS_HOST=127.0.0.1 JARVIS_PORT=8010 .venv/bin/python -m app.main   # loopback only
JARVIS_PORT=8000 .venv/bin/python -m app.main                          # all interfaces
```

> `python -m app.main` previously started nothing — `app/main.py` had no
> `__main__` block, so the Dockerfile's `CMD` was a no-op. Any deployment that
> relied on that command needs re-checking.

### 4. Install on the phone

1. Open `http://<host>:8000/` in the phone's browser.
2. **Android/Chrome** — menu → *Add to Home screen*. **iOS/Safari** — Share →
   *Add to Home Screen*. JARVIS also shows its own install banner.
3. Launch from the home-screen icon: it opens full-screen, without browser chrome.
4. When prompted, **allow notifications** — this needs the service worker to be
   active, so it only appears once step 3 has succeeded.

---

## Verification

Run these from the **phone's browser**, or from any machine that can reach the
host. Each line is a real check with an expected result.

```bash
BASE=http://<host>:8000

# 1. The shell loads (was a 404 before the fix)
curl -s -o /dev/null -w '%{http_code}\n' $BASE/                      # 200

# 2. The service worker carries root scope (without this, push cannot work)
curl -sI $BASE/service-worker.js | grep -i service-worker-allowed     # service-worker-allowed: /

# 3. Every path the worker precaches must exist, or install aborts atomically
for p in / /offline.html /manifest.json /icon-192.png /icon-512.png /badge.png \
         /static/theme.css /static/app.css /static/core.js /static/main.js /static/chat.js; do
  printf '%-22s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' $BASE$p)"
done                                                                  # all 200

# 4. The API answers
curl -s $BASE/api/v1/health                                          # {"status":"healthy",...}

# 5. The console refuses an anonymous caller, and accepts the key
KEY=$(grep '^JARVIS_API_KEY=' .env | cut -d= -f2)
curl -s -o /dev/null -w '%{http_code}\n' $BASE/api/models              # 401
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $KEY" $BASE/api/models   # 200

# 6. ...while the installable surface stays public
curl -s -o /dev/null -w '%{http_code}\n' $BASE/manifest.json           # 200
```

This has been verified on the live tailnet deployment (`rebel`, 2026-09-17):
all twelve app paths returned 200 over `http://rebel.tail4ed6b0.ts.net:8000`,
the console returned 401 anonymously and 200 with the key, and the service
worker reported `activated` with root scope in a real browser at a 390×844
phone viewport.

**In the browser**, the install succeeded when all of these hold:

- `chrome://serviceworker-internals` (or Safari's *Web Inspector → Storage*)
  shows the JARVIS worker **activated**, not *waiting*.
- DevTools → *Application → Manifest* shows the name, icons and no errors.
- The console loads with **no 401s** in the network panel — if it shows 401s,
  the key has not been entered in *Settings → Access* on that device.
- At a 390px viewport there is no horizontal scrolling, the sidebar is
  off-canvas, and the composer text is 16px (below that, iOS zooms on focus).
- With the host stopped, reloading the page shows the offline screen rather than
  a browser error.

The repository's own contract tests pin this surface:

```bash
.venv/bin/pytest tests/contract/test_mobile_pwa.py tests/contract/test_console_auth.py -q
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Phone gets a connection error, curl on the host works | Server bound to loopback only | Start without `JARVIS_HOST`, or set `JARVIS_HOST=0.0.0.0` |
| `http://<ip>:8000/` returns 404 | Running an older tree without the root route | Confirm `curl -s -o /dev/null -w '%{http_code}' .../` is 200; update to a build containing this runbook |
| Install prompt never appears | Service worker not activated | Check `service-worker-allowed: /`; on iOS, Safari only installs via *Add to Home Screen* |
| No notification permission prompt | Worker not active, or the page is not a secure context | Fix the worker first. `localhost` is treated as secure; a plain-HTTP LAN IP is **not** on iOS |
| Notifications to a LAN address never arrive, Tailscale works | Browsers require HTTPS for Push on non-localhost origins | Use the Tailscale option; its HTTPS/MagicDNS path satisfies the secure-context rule |
| Installed app shows a stale UI | Old cache version still active | Bump `CACHE_NAME` in `frontend/assets/service-worker.js`; the worker deletes superseded caches on activate |
| Console loads but every panel is empty | `JARVIS_API_KEY` set on the server, not entered on this device | *Settings → Access* → paste the key → *Save key*; it should report "Key accepted" |
| `JARVIS rejected that API key` | Key entered does not match the server's `JARVIS_API_KEY` | Re-copy from `.env`; the two must be byte-identical |
| Console answered anonymously before this change | Older tree, where the key gated only `/api/upload` | Update to a build containing this runbook; verify with the 401 check above |
| Everything works on the host, phone times out | Firewall blocking the port | Allow inbound TCP 8000 on the host |

---

## Rollback

The change is additive: seven new routes and one new asset. To revert:

```bash
cd /home/sajan/Projects/JARVIS
git revert --no-edit <commit>
```

Reverting restores the previous state, in which `/` returns 404 and the console
is not installable from any device — including the host. That is the pre-change
behaviour, not a regression introduced by the revert.

Nothing in this change writes to the database or migrates state, so no data
rollback is required. To simply stop serving the phone without reverting code,
start the server with `JARVIS_HOST=127.0.0.1`, which makes it loopback-only
again.
