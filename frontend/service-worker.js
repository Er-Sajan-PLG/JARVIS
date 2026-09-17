/**
 * JARVIS Service Worker
 * Handles offline caching and push notifications.
 */

const CACHE_NAME = 'jarvis-v1';
const OFFLINE_URL = '/offline.html';

// Install: cache core assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([
        '/',
        '/static/css/main.css',
        '/static/js/main.js',
        '/static/icon-192.png',
        OFFLINE_URL,
      ]);
    })
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// Fetch: cache-first, then network
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request).then((response) => {
        if (!response || response.status !== 200) return response;

        const responseToCache = response.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseToCache);
        });

        return response;
      });
    }).catch(() => {
      // Return offline page for navigation requests
      if (event.request.mode === 'navigate') {
        return caches.match(OFFLINE_URL);
      }
    })
  );
});

// Push: handle incoming push notifications
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'JARVIS';
  const options = {
    body: data.body || 'New notification',
    icon: data.icon || '/static/icon-192.png',
    badge: data.badge || '/static/badge.png',
    data: data.data || {},
    vibrate: [100, 50, 100],
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// Notification click: open app
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  event.waitUntil(
    clients.openWindow('/')
  );
});
