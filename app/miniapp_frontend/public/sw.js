self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  let data = {
    title: 'Отец прогнозов',
    body: 'Есть новое уведомление.',
    url: '/app',
  };

  try {
    if (event.data) data = { ...data, ...event.data.json() };
  } catch (error) {
    data.body = event.data ? event.data.text() : data.body;
  }

  event.waitUntil(
    self.registration.showNotification(data.title || 'Отец прогнозов', {
      body: data.body || '',
      icon: '/miniapp-static/icons/icon-192.svg',
      badge: '/miniapp-static/icons/icon-192.svg',
      data: { url: data.url || '/app' },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/app';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }

      if (self.clients.openWindow) {
        return self.clients.openWindow(url);
      }

      return undefined;
    })
  );
});
