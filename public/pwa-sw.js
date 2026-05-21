self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  let payload = {};
  if (event.data) {
    try {
      payload = event.data.json();
    } catch (error) {
      payload = { title: 'Sector Momentum Alert', body: event.data.text() };
    }
  }
  const title = payload.title || 'Sector Momentum Alert';
  const options = {
    body: payload.body || 'High-severity state transition detected.',
    tag: payload.tag || 'sector-momentum-alert',
    data: { url: payload.url || '/' }
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data && event.notification.data.url
    ? event.notification.data.url
    : '/';
  event.waitUntil(self.clients.openWindow(targetUrl));
});
