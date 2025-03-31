// Service Worker for Digital Waiter Application
// Version 1.0.0

const CACHE_NAME = 'digital-waiter-cache-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/js/socket_notifications.js',
  '/static/sounds/notification.mp3',
  '/static/img/logo.png',
  '/static/img/badge.png'
];

// Install event - cache assets
self.addEventListener('install', event => {
  console.log('[Service Worker] Installing...');
  
  // Skip waiting to ensure the new service worker activates immediately
  self.skipWaiting();
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[Service Worker] Caching app shell and content');
        return cache.addAll(ASSETS_TO_CACHE);
      })
      .catch(error => {
        console.error('[Service Worker] Cache install error:', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('[Service Worker] Activating...');
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(cacheName => {
          return cacheName !== CACHE_NAME;
        }).map(cacheName => {
          console.log('[Service Worker] Removing old cache:', cacheName);
          return caches.delete(cacheName);
        })
      );
    })
  );
  
  // Ensure the service worker takes control immediately
  return self.clients.claim();
});

// Fetch event - serve from cache, fall back to network
self.addEventListener('fetch', event => {
  // Only cache GET requests
  if (event.request.method !== 'GET') return;
  
  // Skip caching for API requests
  if (event.request.url.includes('/api/')) return;
  
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cached response if found
        if (response) {
          return response;
        }
        
        // Clone the request to use it multiple times
        const fetchRequest = event.request.clone();
        
        return fetch(fetchRequest).then(response => {
          // Check if we received a valid response
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          
          // Clone the response to use it multiple times
          const responseToCache = response.clone();
          
          caches.open(CACHE_NAME)
            .then(cache => {
              cache.put(event.request, responseToCache);
            });
            
          return response;
        });
      })
  );
});

// Push event - handle push notifications
self.addEventListener('push', event => {
  console.log('[Service Worker] Push received');
  
  let data = { title: 'Digital Waiter', body: 'New notification' };
  
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data.body = event.data.text();
    }
  }
  
  const options = {
    body: data.body,
    icon: '/static/img/logo.png',
    badge: '/static/img/badge.png',
    vibrate: [200, 100, 200],
    data: data.data || {},
    requireInteraction: data.requireInteraction || false
  };
  
  if (data.actions) {
    options.actions = data.actions;
  }
  
  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification click event - handle notification clicks
self.addEventListener('notificationclick', event => {
  console.log('[Service Worker] Notification click received', event.notification.tag);
  
  event.notification.close();
  
  // Get the notification data
  const data = event.notification.data;
  
  // Default URL to open
  let targetUrl = '/';
  
  // Set the target URL based on notification type
  if (data.type === 'new_order') {
    targetUrl = '/restaurant/' + data.restaurantId + '/orders';
  } else if (data.type === 'order_status') {
    targetUrl = '/menu/view/' + data.tableId;
  } else if (data.url) {
    // Use the URL from notification data if available
    targetUrl = data.url;
  }
  
  // Handle action buttons if clicked
  if (event.action) {
    if (event.action === 'view_order' && data.orderId) {
      targetUrl = '/order/' + data.orderId + '/receipt';
    } else if (event.action === 'dismiss') {
      // Just close the notification, do nothing else
      return;
    }
  }
  
  event.waitUntil(
    clients.matchAll({ type: 'window' })
      .then(windowClients => {
        // Check if there's already a window open
        for (const client of windowClients) {
          if (client.url === targetUrl && 'focus' in client) {
            return client.focus();
          }
        }
        
        // If no window is open, open a new one
        if (clients.openWindow) {
          return clients.openWindow(targetUrl);
        }
      })
  );
}); 