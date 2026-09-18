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
for (const entry of readdirSync(assets)) {
  const src = join(assets, entry);
  const dest = join(wwwStatic, entry);
  if (rootFiles.includes(entry)) {
    // Also mirrored under /static (harmless duplicate, keeps deep links working).
    cpSync(src, dest, { recursive: true });
  } else if (!existsSync(dest)) {
    cpSync(src, dest, { recursive: true });
  }
}

console.log(`sync-www: bundled console into ${www}`);
