from flask import Blueprint, current_app, request, jsonify
from flask_socketio import emit, join_room, leave_room
from extensions import socketio
import json
from datetime import datetime
import threading
from collections import defaultdict
import os
from pywebpush import webpush, WebPushException

# Create blueprint for push notification routes
push_blueprint = Blueprint('push', __name__, url_prefix='/api/push')

# Dictionary to track connected clients by table/customer
connected_clients = defaultdict(set)
# Dictionary to track customer to table mappings
customer_tables = defaultdict(set)
# Dictionary to cache pending notifications for disconnected clients
notification_cache = defaultdict(list)
# Dictionary to store push subscriptions
push_subscriptions = {}
# Dictionary to track restaurant subscriptions
restaurant_subscriptions = defaultdict(set)

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    current_app.logger.info(f"Socket.IO: New client connected: {request.sid}")
    emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    # Find and remove client from all rooms
    for room_type, rooms in [('table', connected_clients), ('customer', customer_tables)]:
        for room_id, clients in list(rooms.items()):
            if request.sid in clients:
                clients.remove(request.sid)
                current_app.logger.info(f"Socket.IO: Client {request.sid} disconnected from {room_type} {room_id}")
                if not clients:  # If room is empty, clean up
                    rooms.pop(room_id, None)

@socketio.on('subscribe_table')
def handle_table_subscription(data):
    """Subscribe to notifications for a specific table."""
    try:
        table_id = data.get('tableId')
        customer_id = data.get('customerId')
        
        if not table_id:
            emit('error', {'message': 'Table ID is required'})
            return
            
        # Join the table room
        room_name = f"table_{table_id}"
        join_room(room_name)
        connected_clients[table_id].add(request.sid)
        current_app.logger.info(f"Socket.IO: Client {request.sid} subscribed to table {table_id}")
        
        # If customer ID provided, store table mapping
        if customer_id:
            customer_tables[customer_id].add(table_id)
            # Join customer room
            customer_room = f"customer_{customer_id}"
            join_room(customer_room)
            current_app.logger.info(f"Socket.IO: Associated customer {customer_id} with table {table_id}")
            
            # Check for notifications in other tables this customer has been at
            for other_table_id in customer_tables[customer_id]:
                if other_table_id != table_id:
                    other_table_key = f"table_{other_table_id}"
                    if other_table_key in notification_cache and notification_cache[other_table_key]:
                        for notification in notification_cache[other_table_key]:
                            # Clone and modify notification to indicate table
                            notification_copy = notification.copy()
                            if 'body' in notification_copy:
                                notification_copy['body'] += f" (Table {other_table_id})"
                            # Send directly to this client
                            emit('notification', notification_copy)
                            current_app.logger.info(f"Socket.IO: Sent cached notification from table {other_table_id} to customer {customer_id}")
        
        # Check for cached notifications for this table
        table_key = f"table_{table_id}"
        if table_key in notification_cache and notification_cache[table_key]:
            # Send cached notifications to this client
            for notification in notification_cache[table_key]:
                emit('notification', notification)
            # Clear the cache for this table
            notification_cache[table_key] = []
            current_app.logger.info(f"Socket.IO: Sent cached notifications for table {table_id}")
                
        # Send confirmation
        emit('subscribed', {
            'tableId': table_id,
            'message': f'Successfully subscribed to table {table_id}'
        })
        
    except Exception as e:
        current_app.logger.error(f"Socket.IO: Error in table subscription: {e}")
        emit('error', {'message': f'Error subscribing to table: {str(e)}'})

@socketio.on('unsubscribe_table')
def handle_table_unsubscription(data):
    """Unsubscribe from notifications for a specific table."""
    try:
        table_id = data.get('tableId')
        
        if not table_id:
            emit('error', {'message': 'Table ID is required'})
            return
            
        # Leave the table room
        room_name = f"table_{table_id}"
        leave_room(room_name)
        
        # Remove from connected clients
        if table_id in connected_clients and request.sid in connected_clients[table_id]:
            connected_clients[table_id].remove(request.sid)
            current_app.logger.info(f"Socket.IO: Client {request.sid} unsubscribed from table {table_id}")
            
        # Send confirmation
        emit('unsubscribed', {
            'tableId': table_id,
            'message': f'Successfully unsubscribed from table {table_id}'
        })
        
    except Exception as e:
        current_app.logger.error(f"Socket.IO: Error in table unsubscription: {e}")
        emit('error', {'message': f'Error unsubscribing from table: {str(e)}'})

@socketio.on('subscribe_restaurant')
def handle_restaurant_subscription(data):
    """Subscribe to notifications for a specific restaurant."""
    try:
        restaurant_id = data.get('restaurantId')
        
        if not restaurant_id:
            emit('error', {'message': 'Restaurant ID is required'})
            return
            
        # Join the restaurant room
        room_name = f"restaurant_{restaurant_id}"
        join_room(room_name)
        restaurant_subscriptions[restaurant_id].add(request.sid)
        current_app.logger.info(f"Socket.IO: Client {request.sid} subscribed to restaurant {restaurant_id}")
        
        # Send confirmation
        emit('subscribed', {
            'restaurantId': restaurant_id,
            'message': f'Successfully subscribed to restaurant {restaurant_id}'
        })
        
    except Exception as e:
        current_app.logger.error(f"Socket.IO: Error in restaurant subscription: {e}")
        emit('error', {'message': f'Error subscribing to restaurant: {str(e)}'})

@push_blueprint.route('/subscribe', methods=['POST'])
def subscribe_push():
    """Subscribe to push notifications."""
    try:
        data = request.json
        subscription = data.get('subscription')
        user_id = data.get('userId')
        restaurant_id = data.get('restaurantId')
        
        if not subscription:
            return jsonify({'success': False, 'message': 'Subscription data is required'}), 400
            
        # Generate a unique ID for this subscription
        subscription_id = subscription.get('endpoint', '')
        
        # Store the subscription with associated IDs
        push_subscriptions[subscription_id] = {
            'subscription': subscription,
            'user_id': user_id,
            'restaurant_id': restaurant_id
        }
        
        current_app.logger.info(f"Push: New subscription: {subscription_id} (User: {user_id}, Restaurant: {restaurant_id})")
        
        return jsonify({
            'success': True,
            'message': 'Subscription successful'
        })
        
    except Exception as e:
        current_app.logger.error(f"Push: Error in subscription: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@push_blueprint.route('/unsubscribe', methods=['POST'])
def unsubscribe_push():
    """Unsubscribe from push notifications."""
    try:
        data = request.json
        subscription_id = data.get('endpoint')
        user_id = data.get('userId')
        restaurant_id = data.get('restaurantId')
        
        if not (subscription_id or user_id or restaurant_id):
            return jsonify({'success': False, 'message': 'Either subscription endpoint, user ID, or restaurant ID is required'}), 400
            
        # Remove subscription
        if subscription_id and subscription_id in push_subscriptions:
            push_subscriptions.pop(subscription_id)
            current_app.logger.info(f"Push: Removed subscription: {subscription_id}")
            
        # Or remove all subscriptions for a user
        elif user_id:
            for sub_id, sub_data in list(push_subscriptions.items()):
                if sub_data.get('user_id') == user_id:
                    push_subscriptions.pop(sub_id)
                    current_app.logger.info(f"Push: Removed subscription for user: {user_id}")
                    
        # Or remove all subscriptions for a restaurant
        elif restaurant_id:
            for sub_id, sub_data in list(push_subscriptions.items()):
                if sub_data.get('restaurant_id') == restaurant_id:
                    push_subscriptions.pop(sub_id)
                    current_app.logger.info(f"Push: Removed subscription for restaurant: {restaurant_id}")
        
        return jsonify({
            'success': True,
            'message': 'Unsubscription successful'
        })
        
    except Exception as e:
        current_app.logger.error(f"Push: Error in unsubscription: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

def send_notification(notification_type, data, room=None, customer_id=None):
    """
    Send notification to connected clients.
    
    Args:
        notification_type: Type of notification (order_status, new_order, etc.)
        data: Data payload for the notification
        room: Optional room name to send to (e.g., table_1)
        customer_id: Optional customer ID to send to
    """
    try:
        notification = {
            'type': notification_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Add title and body for display
        if notification_type == 'order_status':
            order_id = data.get('orderId')
            new_status = data.get('status')
            notification['title'] = 'Order Update'
            
            if new_status == 'preparing':
                notification['body'] = f'Your order #{order_id} is now being prepared'
            elif new_status == 'ready':
                notification['body'] = f'Your order #{order_id} is ready for pickup!'
            elif new_status == 'completed':
                notification['body'] = f'Your order #{order_id} has been completed. Thank you!'
            else:
                notification['body'] = f'Your order #{order_id} status changed to {new_status}'
                
        elif notification_type == 'new_order':
            notification['title'] = 'New Order'
            notification['body'] = f'New order #{data.get("orderId")} from Table {data.get("tableNumber")}'
        
        current_app.logger.info(f"Socket.IO: Sending {notification_type} notification: {notification['body']}")
        
        # Send to specific room if provided
        if room:
            # Check if any clients are in this room
            if room.startswith('table_'):
                table_id = room.split('_')[1]
                if table_id in connected_clients and connected_clients[table_id]:
                    socketio.emit('notification', notification, room=room)
                    # Play notification sound
                    socketio.emit('play_sound', {}, room=room)
                    current_app.logger.info(f"Socket.IO: Sent notification to room {room}")
                else:
                    # Cache for later delivery
                    notification_cache[room].append(notification)
                    current_app.logger.info(f"Socket.IO: Cached notification for {room} - no connected clients")
                    
                    # Try to send push notification
                    send_push_notification(notification)
            else:
                # For non-table rooms, just send it
                socketio.emit('notification', notification, room=room)
                # Play notification sound
                socketio.emit('play_sound', {}, room=room)
                
        # Send to customer if provided (across all tables)
        elif customer_id:
            customer_room = f"customer_{customer_id}"
            socketio.emit('notification', notification, room=customer_room)
            # Play notification sound
            socketio.emit('play_sound', {}, room=customer_room)
            current_app.logger.info(f"Socket.IO: Sent notification to customer {customer_id}")
            
        # Broadcast if neither room nor customer specified
        else:
            socketio.emit('notification', notification)
            # Play notification sound
            socketio.emit('play_sound', {})
            current_app.logger.info("Socket.IO: Broadcast notification to all clients")
            
    except Exception as e:
        current_app.logger.error(f"Socket.IO: Error sending notification: {e}")

def send_push_notification(notification):
    """Send web push notification to subscribed endpoints."""
    try:
        # Get VAPID keys from app config
        vapid_private_key = current_app.config.get('VAPID_PRIVATE_KEY')
        vapid_claim_email = current_app.config.get('VAPID_CLAIM_EMAIL')
        
        if not vapid_private_key or not vapid_claim_email:
            current_app.logger.error("Push: VAPID keys not configured")
            return
            
        # Prepare VAPID claims
        vapid_claims = {
            "sub": f"mailto:{vapid_claim_email}"
        }
        
        # Send to all relevant subscriptions
        for subscription_id, subscription_data in push_subscriptions.items():
            try:
                webpush(
                    subscription_info=subscription_data['subscription'],
                    data=json.dumps(notification),
                    vapid_private_key=vapid_private_key,
                    vapid_claims=vapid_claims
                )
                current_app.logger.info(f"Push: Notification sent to {subscription_id}")
            except WebPushException as e:
                # If the subscription is expired or invalid, remove it
                if e.response and e.response.status_code in [404, 410]:
                    current_app.logger.info(f"Push: Removing expired subscription: {subscription_id}")
                    push_subscriptions.pop(subscription_id, None)
                else:
                    current_app.logger.error(f"Push: Error sending to {subscription_id}: {e}")
            except Exception as e:
                current_app.logger.error(f"Push: Error with subscription {subscription_id}: {e}")
                
    except Exception as e:
        current_app.logger.error(f"Push: General error sending push notification: {e}")

# Order status change notification
def notify_order_status_change(order, old_status, new_status):
    """Notify customers about order status changes."""
    try:
        from models import Order, Table

        # Verify we have a valid order object with an ID
        if not order or not hasattr(order, 'id') or not order.id:
            current_app.logger.error(f"Socket.IO: Invalid order object for status change notification: {order}")
            return
            
        # Refresh order to ensure it's attached to the session
        order_id = order.id
        try:
            refreshed_order = Order.query.get(order_id)
            if not refreshed_order:
                current_app.logger.error(f"Socket.IO: Could not refresh order {order_id}")
                return
        except Exception as e:
            current_app.logger.error(f"Socket.IO: Error refreshing order {order_id}: {e}")
            return
            
        # Get table info safely
        table_number = "Unknown"
        table_id = None
        
        if refreshed_order.table_id:
            try:
                table = Table.query.get(refreshed_order.table_id)
                if table:
                    table_number = table.number
                    table_id = table.id
            except Exception as e:
                current_app.logger.error(f"Socket.IO: Error getting table for order {order_id}: {e}")
                
        if not table_id:
            current_app.logger.warning(f"Socket.IO: Order {order_id} has no valid table information")
            return
            
        # Prepare notification data
        notification_data = {
            'orderId': refreshed_order.id,
            'tableNumber': table_number,
            'tableId': table_id,
            'status': new_status,
            'oldStatus': old_status,
            'updated_at': refreshed_order.updated_at.isoformat() if hasattr(refreshed_order, 'updated_at') and refreshed_order.updated_at else datetime.utcnow().isoformat()
        }
        
        # Send to the table's room
        room_name = f"table_{table_id}"
        current_app.logger.info(f"Socket.IO: Sending order status notification to {room_name}: {old_status} -> {new_status}")
        send_notification('order_status', notification_data, room=room_name)
        
    except Exception as e:
        current_app.logger.error(f"Socket.IO: Error in notify_order_status_change: {e}")

# Notify restaurant about new order
def notify_restaurant_new_order(order):
    """Notify restaurant about new orders."""
    try:
        if not order or not hasattr(order, 'id') or not order.id:
            current_app.logger.error(f"Socket.IO: Invalid order object for new order notification: {order}")
            return
            
        restaurant_id = order.user_id
        
        if not restaurant_id:
            current_app.logger.error(f"Socket.IO: Order {order.id} has no restaurant ID")
            return
            
        # Prepare notification data - safely
        try:
            table_number = "Unknown"
            table_id = None
            if order.table:
                table_number = order.table.number
                table_id = order.table_id
                
            items_data = []
            for item in order.items:
                try:
                    if item.menu_item:
                        items_data.append({
                            'name': item.menu_item.name,
                            'quantity': item.quantity
                        })
                except Exception as e:
                    current_app.logger.error(f"Socket.IO: Error processing menu item for notification: {e}")
                
            notification_data = {
                'orderId': order.id,
                'tableNumber': table_number,
                'tableId': table_id,
                'items': items_data,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Send to restaurant room
            room_name = f"restaurant_{restaurant_id}"
            current_app.logger.info(f"Socket.IO: Sending new order notification to {room_name} for order {order.id}")
            send_notification('new_order', notification_data, room=room_name)
        except Exception as e:
            current_app.logger.error(f"Socket.IO: Error preparing notification data: {e}")
        
    except Exception as e:
        current_app.logger.error(f"Socket.IO: Error in notify_restaurant_new_order: {e}")

# Notify customer about order status change
def notify_customer_order_status(order, new_status):
    """Notify customer about order status changes."""
    try:
        if not order.table_id:
            current_app.logger.error(f"Socket.IO: Order {order.id} has no table ID")
            return
            
        # Prepare notification data
        notification_data = {
            'orderId': order.id,
            'tableNumber': order.table.number if order.table else 'Unknown',
            'status': new_status,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Send to table room
        room_name = f"table_{order.table_id}"
        send_notification('order_status', notification_data, room=room_name)
        
    except Exception as e:
        current_app.logger.error(f"Socket.IO: Error in notify_customer_order_status: {e}")

# Register SQLAlchemy event listeners for order status changes
def register_notification_handlers():
    """Register SQLAlchemy event listeners for notifications."""
    from models import Order, db
    
    @db.event.listens_for(Order.status, 'set')
    def order_status_change(target, value, oldvalue, initiator):
        if oldvalue != value:
            current_app.logger.info(f"Socket.IO: Order {target.id if hasattr(target, 'id') else None} status change: {oldvalue} -> {value}")
            
            # Create a copy of current_app for the thread
            app = current_app._get_current_object()
            
            # Run in a separate thread to avoid blocking
            def run_with_context():
                with app.app_context():
                    try:
                        notify_order_status_change(target, oldvalue, value)
                    except Exception as e:
                        app.logger.error(f"Socket.IO: Error in status change notification thread: {e}")
                    
            threading.Thread(
                target=run_with_context,
                name="socket_notify_status_change"
            ).start() 