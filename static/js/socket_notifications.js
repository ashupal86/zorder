// Socket.IO notifications client
class SocketNotificationManager {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.tableId = null;
        this.customerId = null;
        this.notificationHandlers = [];
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000; // 2 seconds
        this.soundEnabled = true;
        this.notificationSound = new Audio('/static/sounds/notification.mp3');
        this.loadSettings();
        this.eventListeners = {};
        this.pushSupported = false;
        this.pushRegistration = null;
    }

    // Initialize the Socket.IO connection
    init() {
        // Get the customer ID from local storage or generate a new one
        this.customerId = localStorage.getItem('customerId');
        if (!this.customerId) {
            this.customerId = 'customer_' + Math.random().toString(36).substring(2, 15);
            localStorage.setItem('customerId', this.customerId);
            console.log('Generated new customer ID:', this.customerId);
        }

        // Connect to Socket.IO server
        this.socket = io();
        
        // Set up event listeners
        this.socket.on('connect', () => {
            console.log('Socket.IO: Connected to server');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            
            // If we have a table ID, subscribe immediately
            if (this.tableId) {
                this.subscribeToTable(this.tableId);
            }
            
            // Dispatch connection event for any listeners
            this.dispatchEvent('connected', { status: 'connected' });
        });
        
        this.socket.on('disconnect', () => {
            console.log('Socket.IO: Disconnected from server');
            this.isConnected = false;
            this.handleDisconnect();
        });
        
        this.socket.on('error', (error) => {
            console.error('Socket.IO: Error:', error);
            this.dispatchEvent('error', error);
        });
        
        this.socket.on('notification', (notification) => {
            console.log('Socket.IO: Received notification:', notification);
            this.handleNotification(notification);
        });
        
        this.socket.on('subscribed', (data) => {
            console.log('Socket.IO: Subscribed to table:', data);
            this.dispatchEvent('subscribed', data);
        });
        
        this.socket.on('unsubscribed', (data) => {
            console.log('Socket.IO: Unsubscribed from table:', data);
            this.dispatchEvent('unsubscribed', data);
        });
        
        this.socket.on('play_sound', (data) => {
            this.playNotificationSound();
        });
        
        this.setupPushNotifications();
    }
    
    // Load user settings from localStorage
    loadSettings() {
        // Load sound preferences
        const soundSetting = localStorage.getItem('notificationSoundEnabled');
        if (soundSetting !== null) {
            this.soundEnabled = soundSetting === 'true';
        }
    }
    
    // Subscribe to notifications for a specific table
    subscribeToTable(tableId) {
        if (!this.isConnected) {
            console.warn('Socket.IO: Cannot subscribe, not connected');
            this.tableId = tableId; // Save for when we connect
            return;
        }
        
        console.log(`Socket.IO: Subscribing to table ${tableId} with customer ID ${this.customerId}`);
        this.tableId = tableId;
        
        this.socket.emit('subscribe_table', {
            tableId: tableId,
            customerId: this.customerId
        });
    }
    
    // Unsubscribe from notifications for a specific table
    unsubscribeFromTable(tableId) {
        if (!this.isConnected) {
            console.warn('Socket.IO: Cannot unsubscribe, not connected');
            return;
        }
        
        console.log(`Socket.IO: Unsubscribing from table ${tableId}`);
        
        this.socket.emit('unsubscribe_table', {
            tableId: tableId
        });
        
        // If this is our current table, clear it
        if (this.tableId === tableId) {
            this.tableId = null;
        }
    }
    
    // Handle a received notification
    handleNotification(notification) {
        // Play notification sound if enabled
        this.playNotificationSound();
        
        // Dispatch the notification to registered handlers
        this.dispatchEvent('notification', notification);
        
        // Show browser notification if available and permitted
        this.showBrowserNotification(notification);
    }
    
    // Play notification sound with fallback and auto-play restrictions handling
    playNotificationSound() {
        if (!this.soundEnabled) {
            return;
        }
        
        try {
            // Use only one sound file for all notification types
            const soundFile = '/static/sounds/notification.mp3';
            
            // Try to play the notification sound
            const playPromise = new Audio(soundFile).play();
            
            // Modern browsers return a promise from play()
            if (playPromise !== undefined) {
                playPromise.catch(error => {
                    if (error.name === 'NotAllowedError') {
                        console.warn('Sound play was prevented by browser autoplay policy. Will try on next user interaction.');
                        
                        // Set up a one-time event listener for user interaction
                        const setupAutoplayFix = () => {
                            const fixAutoplay = () => {
                                // Create and play a silent sound to unblock audio
                                const silentSound = new Audio('/static/sounds/silent.mp3');
                                silentSound.play().then(() => {
                                    console.log('Audio autoplay unblocked');
                                }).catch(e => {
                                    console.error('Failed to unblock autoplay', e);
                                });
                                
                                // Remove the event listeners
                                document.removeEventListener('click', fixAutoplay);
                                document.removeEventListener('touchstart', fixAutoplay);
                            };
                            
                            document.addEventListener('click', fixAutoplay, { once: true });
                            document.addEventListener('touchstart', fixAutoplay, { once: true });
                        };
                        
                        setupAutoplayFix();
                    } else {
                        console.error('Error playing notification sound:', error);
                    }
                });
            }
        } catch (error) {
            console.error('Failed to play notification sound:', error);
        }
    }
    
    // Show a browser notification if available
    showBrowserNotification(notification) {
        // Check if browser notifications are supported
        if (!('Notification' in window)) {
            return;
        }
        
        // Check if permission is granted
        if (Notification.permission === 'granted') {
            this.createBrowserNotification(notification);
        } 
        // Ask for permission if not determined
        else if (Notification.permission !== 'denied') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    this.createBrowserNotification(notification);
                }
            });
        }
    }
    
    // Create and display a browser notification
    createBrowserNotification(notification) {
        try {
            const title = notification.title || 'Notification';
            const options = {
                body: notification.body || JSON.stringify(notification.data),
                icon: '/static/images/logo.png'
            };
            
            const browserNotification = new Notification(title, options);
            
            // Close the notification after 5 seconds
            setTimeout(() => {
                browserNotification.close();
            }, 5000);
            
            // Handle notification click
            browserNotification.onclick = function() {
                window.focus();
                browserNotification.close();
            };
        } catch (error) {
            console.error('Error showing browser notification:', error);
        }
    }
    
    // Handle reconnection attempts
    handleDisconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * this.reconnectAttempts;
            
            console.log(`Socket.IO: Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                if (!this.isConnected) {
                    console.log('Socket.IO: Attempting to reconnect...');
                    this.socket.connect();
                }
            }, delay);
        } else {
            console.error('Socket.IO: Maximum reconnection attempts reached');
            this.dispatchEvent('error', { 
                message: 'Failed to reconnect to notification server after maximum attempts'
            });
        }
    }
    
    // Add a notification event handler
    addEventListener(event, handler) {
        if (!this.eventListeners[event]) {
            this.eventListeners[event] = [];
        }
        this.eventListeners[event].push(handler);
    }
    
    // Remove a notification event handler
    removeEventListener(event, handler) {
        if (this.eventListeners[event]) {
            this.eventListeners[event] = this.eventListeners[event].filter(
                item => !(item === handler)
            );
        }
    }
    
    // Dispatch event to registered handlers
    dispatchEvent(event, data) {
        if (this.eventListeners[event]) {
            this.eventListeners[event].forEach(item => {
                try {
                    item(data);
                } catch (error) {
                    console.error(`Socket.IO: Error in ${event} event handler:`, error);
                }
            });
        }
    }
    
    // Toggle notification sound
    toggleSound(enabled) {
        this.soundEnabled = enabled;
        localStorage.setItem('notificationSoundEnabled', enabled);
    }
    
    // Disconnect from the Socket.IO server
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.isConnected = false;
        }
    }
    
    setupPushNotifications() {
        // Check if Push API is supported
        if ('serviceWorker' in navigator && 'PushManager' in window) {
            this.pushSupported = true;
            
            // Register service worker
            navigator.serviceWorker.register('/static/js/service-worker.js')
                .then(registration => {
                    console.log('Service Worker registered with scope:', registration.scope);
                    this.pushRegistration = registration;
                    
                    // Check for existing permissions
                    this.checkPushNotificationPermission();
                })
                .catch(error => {
                    console.error('Service Worker registration failed:', error);
                });
        } else {
            console.log('Push notifications not supported in this browser');
        }
    }
    
    checkPushNotificationPermission() {
        if (!this.pushSupported) return;
        
        if (Notification.permission === 'granted') {
            console.log('Push notification permission already granted');
            this.subscribeToPushNotifications();
        } else if (Notification.permission !== 'denied') {
            // We need to ask for permission
            document.getElementById('enable-notifications-btn')?.classList.remove('d-none');
        }
    }
    
    requestPushNotificationPermission() {
        if (!this.pushSupported) return Promise.reject('Push notifications not supported');
        
        return Notification.requestPermission()
            .then(permission => {
                if (permission === 'granted') {
                    document.getElementById('enable-notifications-btn')?.classList.add('d-none');
                    return this.subscribeToPushNotifications();
                } else {
                    return Promise.reject('Permission denied');
                }
            });
    }
    
    subscribeToPushNotifications() {
        if (!this.pushRegistration) return Promise.reject('No service worker registration');
        
        const publicVapidKey = 'BFr9QolZnRnLBxhPwz4l0WdZzBqhJO8XEohkJkwdXRJ2jjFuD5KPp5U2aHQJj0DgZmQw7sqw7IzRpnrP-ohO19s';
        
        return this.pushRegistration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: this.urlBase64ToUint8Array(publicVapidKey)
        })
        .then(subscription => {
            console.log('User is subscribed to push notifications');
            
            // Send the subscription to server
            return fetch('/api/push/subscribe', {
                method: 'POST',
                body: JSON.stringify(subscription),
                headers: {
                    'Content-Type': 'application/json'
                }
            });
        })
        .then(response => response.json())
        .then(data => {
            console.log('Push subscription sent to server:', data);
            return data;
        })
        .catch(error => {
            console.error('Failed to subscribe to push notifications:', error);
            return Promise.reject(error);
        });
    }
    
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
    
    handlePlaySound(data) {
        this.playNotificationSound();
    }
    
    subscribeToRestaurant(restaurantId) {
        if (!this.socket) return;
        
        this.socket.emit('subscribe_restaurant', { restaurantId });
    }
    
    notify(title, options = {}) {
        // Check browser notification support
        if (!('Notification' in window)) {
            console.warn('This browser does not support desktop notifications');
            return;
        }
        
        // Check permission
        if (Notification.permission === 'granted') {
            this.createNotification(title, options);
        } else if (Notification.permission !== 'denied') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    this.createNotification(title, options);
                }
            });
        }
    }
    
    createNotification(title, options = {}) {
        const notification = new Notification(title, options);
        
        // Add click event
        if (options.click) {
            notification.onclick = options.click;
        } else {
            notification.onclick = () => {
                window.focus();
                notification.close();
            };
        }
        
        return notification;
    }
}

// Create and export a singleton instance
const notificationManager = new SocketNotificationManager();

// Create the service worker file on window load
window.addEventListener('load', () => {
    // Add a button to the UI for enabling notifications if needed
    if ('Notification' in window && Notification.permission !== 'granted' && Notification.permission !== 'denied') {
        const header = document.querySelector('nav.navbar');
        if (header) {
            const notificationBtn = document.createElement('button');
            notificationBtn.id = 'enable-notifications-btn';
            notificationBtn.className = 'btn btn-sm btn-outline-warning ms-2 d-none';
            notificationBtn.innerHTML = '<i class="fas fa-bell me-1"></i> Enable Notifications';
            notificationBtn.onclick = () => notificationManager.requestPushNotificationPermission();
            
            header.querySelector('.container').appendChild(notificationBtn);
        }
    }
}); 