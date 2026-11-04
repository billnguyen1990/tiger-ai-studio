const CACHE_NAME = 'finance-app-v70';
const urlsToCache = [
  '/tai-chinh',
  '/manifest.json',
  '/app-icon-v56.png'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
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
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  // Redirect root or index.html to cached /tai-chinh if offline
  if (url.pathname === '/index.html' || url.pathname === '/') {
    event.respondWith(
      caches.match('/tai-chinh').then(cached => {
        return cached || fetch('/tai-chinh').catch(() => caches.match('/tai-chinh'));
      })
    );
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then(response => {
        return response || fetch(event.request).catch(err => {
          if (event.request.mode === 'navigate') {
            return caches.match('/tai-chinh');
          }
          throw err;
        });
      })
  );
});
