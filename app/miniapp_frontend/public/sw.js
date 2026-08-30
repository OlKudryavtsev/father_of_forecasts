const APP_VERSION = '3.9.15';
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});
self.addEventListener('install', (event) => {
  self.skipWaiting();
});
self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});
self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.pathname === '/miniapp-static/app-version.json') {
    event.respondWith(new Response(JSON.stringify({ version: APP_VERSION }), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } }));
  }
});
