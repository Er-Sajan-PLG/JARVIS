/* Copies the served web console into mobile/www so Capacitor bundles it.
 *
 * Layout mirrors what app/main.py serves:
 *   /                  <- frontend/index.html
 *   /offline.html      <- frontend/offline.html
 *   /manifest.json, /service-worker.js, /icon-*.png, /badge.png
 *                      <- frontend/assets/*
 *   /static/*          <- frontend/assets/*  (mounted at /static)
 *
 * Absolute paths (/static/...) keep working because www/ is served as the
 * WebView root (capacitor://localhost/).
 */
import { cpSync, existsSync, mkdirSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const frontend = join(here, '..', '..', 'frontend');
const assets = join(frontend, 'assets');
const www = join(here, '..', 'www');
const wwwStatic = join(www, 'static');

mkdirSync(wwwStatic, { recursive: true });

for (const f of ['index.html', 'offline.html']) {
  cpSync(join(frontend, f), join(www, f));
}

const rootFiles = ['manifest.json', 'service-worker.js', 'icon-192.png', 'icon-512.png', 'badge.png'];
for (const f of rootFiles) {
  const src = join(assets, f);
  if (existsSync(src)) cpSync(src, join(www, f));
  else console.warn(`sync-www: missing ${src} (skipped)`);
}

// Everything in assets/ is reachable under /static/* on the server.
// Always overwrite: stale bundles are worse than slow copies (a skipped
// copy once shipped an APK with the previous release's JS).
for (const entry of readdirSync(assets)) {
  cpSync(join(assets, entry), join(wwwStatic, entry), { recursive: true });
}

console.log(`sync-www: bundled console into ${www}`);

// Refresh the connection candidates the app probes at boot: the stable
// tailnet name first, then this machine's current LAN IPs (DHCP moves them,
// so they are a snapshot, not a promise). The stored operator URL always
// wins — these are fallbacks.
{
  const { networkInterfaces } = await import('node:os');
  const { readFileSync, writeFileSync, existsSync: exists } = await import('node:fs');
  const found = [];
  try {
    const env = readFileSync(join(here, '..', '..', '.env'), 'utf8');
    const m = env.match(/^JARVIS_PUBLIC_ORIGIN=(.+)$/m);
    if (m) found.push(m[1].trim().replace(/\/+$/, ''));
  } catch { /* no .env: tailnet candidate skipped */ }
  for (const ifs of Object.values(networkInterfaces())) {
    for (const nic of ifs || []) {
      if (nic.family === 'IPv4' && !nic.internal && nic.address.startsWith('192.168.')) {
        found.push(`http://${nic.address}:8000`);
      }
    }
  }
  const dest = join(wwwStatic, 'server-candidates.json');
  let merged = [...found];
  try {
    const prev = JSON.parse(readFileSync(dest, 'utf8'));
    for (const u of prev) if (!merged.includes(u)) merged.push(u);
  } catch { /* fresh bundle */ }
  writeFileSync(dest, JSON.stringify(merged, null, 2) + '\n');
  // Mirror back to the source tree so web/PWA serves the same snapshot.
  try {
    writeFileSync(join(assets, 'server-candidates.json'), JSON.stringify(merged, null, 2) + '\n');
  } catch { /* read-only source: APK still got its copy */ }
  console.log(`sync-www: candidates: ${merged.join(', ') || '(none)'}`);
}
