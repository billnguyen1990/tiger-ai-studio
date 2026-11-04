const CACHE_NAME = 'finance-app-v103-nocache';
const urlsToCache = [
  '/tai-chinh',
  '/manifest.json',
  '/app-icon-v56.png'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(urlsToCache).catch(err => {
        console.warn('SW cache addAll warning:', err);
      });
    })
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cache => {
          if (cache !== CACHE_NAME) {
            console.log('Purging old cache:', cache);
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim()).then(() => {
      // Force all open clients to reload to load new clean UI immediately
      return self.clients.matchAll({ type: 'window' }).then(clients => {
        clients.forEach(client => {
          if (client.url && 'navigate' in client) {
            client.navigate(client.url);
          }
        });
      });
    })
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // NETWORK-FIRST FOR NAVIGATION & HTML (ALWAYS FETCH LATEST FROM SERVER)
  if (event.request.mode === 'navigate' || event.request.headers.get('accept')?.includes('text/html') || url.pathname === '/tai-chinh') {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => {
          // Fallback to cache only when truly offline
          return caches.match(event.request).then(cached => cached || caches.match('/tai-chinh'));
        })
    );
    return;
  }

  // Network first for static assets as well to avoid stale caching
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
