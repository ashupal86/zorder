/**
 * 
 * Notification Manager for Digital Waiter Application
 * Handles socket connections, push notifications, and sound alerts
 */
class NotificationManager {
  constructor() {
    this.socket = null;
    this.connected = false;
    this.events = {};
    this.swRegistration = null;
    this.pushSubscription = null;
    this.userId = null;
    this.restaurantId = null;
  }

  // Initialize the notification manager
  init() {
    // Connect to socket server
    this.connectSocket();
    
    // Check if service workers are supported
    if ('serviceWorker' in navigator && 'PushManager' in window) {
      this.initServiceWorker();
    } else {
      console.warn('Push notifications are not supported in this browser');
    }
  }

  // Register the service worker for push notifications
  async initServiceWorker() {
    try {
      const swRegistration = await navigator.serviceWorker.register('/static/js/service-worker.js');
      this.swRegistration = swRegistration;
      console.log('Service Worker registered successfully:', swRegistration);
      
      // Check permission and subscribe to push notifications if allowed
      this.checkPushPermission();
    } catch (error) {
      console.error('Service Worker registration failed:', error);
    }
  }

  // Connect to the socket server
  connectSocket() {
    // Create socket connection
    this.socket = io();
    
    // Handle socket connection events
    this.socket.on('connect', () => {
      console.log('Connected to notification server');
      this.connected = true;
      this.trigger('connected');
    });
    
    this.socket.on('disconnect', () => {
      console.log('Disconnected from notification server');
      this.connected = false;
      this.trigger('disconnected');
    });
    
    // Handle incoming notifications
    this.socket.on('notification', (data) => {
      console.log('Received notification:', data);
      this.trigger('notification', data);
    });
    
    // Handle sound notifications
    this.socket.on('play_sound', (data) => {
      this.playSound();
    });
  }

  // Subscribe to restaurant-specific notifications
  subscribeToRestaurant(restaurantId) {
    if (!this.connected || !restaurantId) return;
    
    this.restaurantId = restaurantId;
    this.socket.emit('subscribe_restaurant', {
      restaurantId: restaurantId
    });
    
    console.log(`Subscribed to restaurant ${restaurantId} notifications`);
  }

  // Subscribe to user-specific notifications
  subscribeToUser(userId) {
    if (!this.connected || !userId) return;
    
    this.userId = userId;
    this.socket.emit('subscribe_user', {
      userId: userId
    });
    
    console.log(`Subscribed to user ${userId} notifications`);
  }

  // Check push notification permission
  checkPushPermission() {
    if (!this.swRegistration) return;
    
    // Check current permission status
    if (Notification.permission === 'granted') {
      console.log('Push notifications already permitted');
      this.subscribeToPushNotifications();
    } else if (Notification.permission !== 'denied') {
      this.requestNotificationPermission();
    } else {
      console.log('Push notifications permission denied');
    }
  }

  // Request permission for push notifications
  async requestNotificationPermission() {
    try {
      const permission = await Notification.requestPermission();
      
      if (permission === 'granted') {
        console.log('Notification permission granted');
        this.subscribeToPushNotifications();
      } else {
        console.log('Notification permission denied');
      }
    } catch (error) {
      console.error('Error requesting notification permission:', error);
    }
  }

  // Subscribe to push notifications
  async subscribeToPushNotifications() {
    if (!this.swRegistration) return;
    
    try {
      // Get the push subscription if it exists, or create a new one
      const existingSubscription = await this.swRegistration.pushManager.getSubscription();
      
      if (existingSubscription) {
        this.pushSubscription = existingSubscription;
        console.log('Using existing push subscription');
        this.sendSubscriptionToServer(existingSubscription);
        return;
      }
      
      // Create a new subscription
      const publicVapidKey = document.querySelector('meta[name="vapid-public-key"]')?.content;
      
      if (!publicVapidKey) {
        console.error('VAPID public key not found');
        return;
      }
      
      const subscription = await this.swRegistration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: this.urlBase64ToUint8Array(publicVapidKey)
      });
      
      this.pushSubscription = subscription;
      console.log('Created new push subscription');
      
      // Send the subscription to the server
      this.sendSubscriptionToServer(subscription);
    } catch (error) {
      console.error('Failed to subscribe to push notifications:', error);
    }
  }

  // Send the push subscription to the server
  async sendSubscriptionToServer(subscription) {
    try {
      const response = await fetch('/api/push/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          subscription: subscription,
          userId: this.userId,
          restaurantId: this.restaurantId
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        console.log('Push subscription saved on server');
      } else {
        console.error('Failed to save push subscription:', data.message);
      }
    } catch (error) {
      console.error('Error sending push subscription to server:', error);
    }
  }

  // Unsubscribe from push notifications
  async unsubscribeFromPushNotifications() {
    if (!this.pushSubscription) return;
    
    try {
      const success = await this.pushSubscription.unsubscribe();
      
      if (success) {
        this.pushSubscription = null;
        console.log('Unsubscribed from push notifications');
        
        // Notify the server
        await fetch('/api/push/unsubscribe', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            userId: this.userId,
            restaurantId: this.restaurantId
          })
        });
      }
    } catch (error) {
      console.error('Error unsubscribing from push notifications:', error);
    }
  }

  // Helper method to convert base64 to Uint8Array for VAPID key
  urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
      .replace(/-/g, '+')
      .replace(/_/g, '/');
    
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    
    return outputArray;
  }

  // Play a notification sound - simplified to use only one sound file
  playSound() {
    try {
      const audio = new Audio('/static/sounds/notification.mp3');
      audio.play().catch(error => {
        console.error('Error playing sound:', error);
      });
    } catch (error) {
      console.error('Error creating audio object:', error);
    }
  }

  // Event system methods
  addEventListener(event, callback) {
    if (!this.events[event]) {
      this.events[event] = [];
    }
    
    this.events[event].push(callback);
  }

  removeEventListener(event, callback) {
    if (!this.events[event]) return;
    
    this.events[event] = this.events[event].filter(cb => cb !== callback);
  }

  trigger(event, data) {
    if (!this.events[event]) return;
    
    this.events[event].forEach(callback => {
      try {
        callback(data);
      } catch (error) {
        console.error(`Error in ${event} event handler:`, error);
      }
    });
  }
}

// Create a global instance of the notification manager
const notificationManager = new NotificationManager(); 