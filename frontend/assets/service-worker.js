/**
 * JARVIS Service Worker
 *
 * Two responsibilities:
 *   1. Keep the console shell installable and usable when the host is asleep.
 *   2. Receive Web Push notifications and focus the app when one is tapped.
 *
 * Caching policy: the shell is network-first so a running host always wins and
 * an updated UI is never masked by a stale cache; the cache is the fallback
 * when the host is unreachable. API traffic is never cached -- a cached
 * /api/... response would replay stale conversation and settings data.
 */

const CACHE_NAME = 'jarvis-shell-v2';
const OFFLINE_URL = '/offline.html';

// Precached at install. `cache.addAll` is atomic: a single 404 aborts the whole
// install, the worker never activates, and push (which requires an active
// worker) silently stops working. Every path here must return 200.
const PRECACHE_URLS = [
  '/',
  OFFLINE_URL,
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png',
  '/badge.png',
  '/static/theme.css',
  '/static/app.css',
  '/static/core.js',
  '/static/main.js',
  '/static/chat.js',
];

const PRECACHE_PATHS = new Set(PRECACHE_URLS);

/** Requests whose responses must never be cached or served from cache. */
function isBypassed(url) {
  return (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/ws') ||
    url.pathname.startsWith('/metrics') ||
    url.pathname === '/ready'
  );
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      // Add individually so one missing optional asset cannot abort the install
      // and leave the app uninstallable. '/' and the offline page are required.
      await Promise.all(
        PRECACHE_URLS.map(async (path) => {
          try {
            await cache.add(new Request(path, { cache: 'reload' }));
          } catch (err) {
            if (path === '/' || path === OFFLINE_URL) throw err;
            console.warn('[SW] optional precache miss:', path, err);
          }
        })
      );
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (isBypassed(url)) return;

  // Navigations: network-first, fall back to the cached shell, then offline page.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put('/', copy)).catch(() => {});
          return response;
        })
        .catch(async () => {
          const cache = await caches.open(CACHE_NAME);
          return (await cache.match('/')) || (await cache.match(OFFLINE_URL)) || Response.error();
        })
    );
    return;
  }

  // Static assets: cache-first with a background refresh.
  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response && response.status === 200 && response.type === 'basic') {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy)).catch(() => {});
          }
          return response;
        })
        .catch(() => cached || Response.error());

      const isPrecached = PRECACHE_PATHS.has(url.pathname);
      return isPrecached && cached ? cached : network;
    })
  );
});

// ── Web Push ────────────────────────────────────────────────────────────────

self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : '' };
  }

  const title = data.title || 'JARVIS';
  const options = {
    body: data.body || 'New notification',
    icon: data.icon || '/icon-192.png',
    badge: data.badge || '/badge.png',
    data: data.data || {},
    vibrate: [100, 50, 100],
    tag: data.tag || 'jarvis',
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Focus an open JARVIS tab rather than opening a duplicate.
      for (const client of clientList) {
        if (new URL(client.url).origin === self.location.origin && 'focus' in client) {
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    })
  );
});
