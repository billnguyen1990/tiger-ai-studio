const CACHE_NAME = 'finance-app-v66';
const urlsToCache = [
  './',
  './index.html',
  './manifest.json',
  './app-icon-v56.png',
  './assets/trading_chart.png',
  './assets/crypto_astronaut.png',
  './assets/money_falling.png',
  './assets/money_stacks.png',
  './assets/gold_bars.png',
  './assets/cal_aurora.jpg',
  './assets/cal_sunset.jpg'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
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
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        return response || fetch(event.request);
      })
  );
});

