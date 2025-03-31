from flask import Blueprint, current_app, request, jsonify
from flask_socketio import emit, join_room, leave_room
from extensions import socketio
import json
from datetime import datetime
import logging

# Create blueprint for notification routes
notification_bp = Blueprint('notification', __name__, url_prefix='/api/notification')

# Configure logging
logger = logging.getLogger('socketio')
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Store connected clients and notification cache
connected_clients = {}  # table_id -> list of socket IDs
notification_cache = {}  # room -> list of notifications

# ===== Helper Functions =====
def get_status_message(order_id, table_number, status):
    """Get a human-readable message for an order status."""
    status_messages = {
        'pending': f'Order #{order_id} from Table {table_number} is pending',
        'preparing': f'Order #{order_id} from Table {table_number} is being prepared',
        'ready': f'Order #{order_id} from Table {table_number} is ready for pickup',
        'completed': f'Order #{order_id} from Table {table_number} has been completed',
        'cancelled': f'Order #{order_id} from Table {table_number} has been cancelled'
    }
    return status_messages.get(status, f'Order #{order_id} status updated to {status}')

# ===== Room Management =====
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info(f"Socket connected: {request.sid}")
    emit('connected', {'status': 'connected', 'sid': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info(f"Socket disconnected: {request.sid}")
    
    # Remove client from connected_clients
    for table_id, clients in connected_clients.items():
        if request.sid in clients:
            clients.remove(request.sid)
            logger.info(f"Removed client {request.sid} from table {table_id}")

@socketio.on('join_restaurant')
def handle_join_restaurant(data):
    """Join a restaurant room to receive notifications for a specific restaurant."""
    try:
        restaurant_id = data.get('restaurant_id')
        if not restaurant_id:
            emit('error', {'message': 'Restaurant ID is required'})
            return
            
        room = f"restaurant_{restaurant_id}"
        join_room(room)
        logger.info(f"Client {request.sid} joined room: {room}")
        
        # Send cached notifications if any
        if room in notification_cache and notification_cache[room]:
            for notification in notification_cache[room]:
                emit('notification', notification)
                
        emit('room_joined', {
            'room': room,
            'restaurant_id': restaurant_id
        })
    except Exception as e:
        logger.error(f"Error joining restaurant room: {str(e)}")
        emit('error', {'message': str(e)})

@socketio.on('join_table')
def handle_join_table(data):
    """Join a table room to receive notifications for a specific table."""
    try:
        table_id = data.get('table_id')
        if not table_id:
            emit('error', {'message': 'Table ID is required'})
            return
            
        room = f"table_{table_id}"
        join_room(room)
        
        # Add client to connected_clients
        if table_id not in connected_clients:
            connected_clients[table_id] = []
        if request.sid not in connected_clients[table_id]:
            connected_clients[table_id].append(request.sid)
            
        logger.info(f"Client {request.sid} joined room: {room}")
        
        # Send cached notifications if any
        if room in notification_cache and notification_cache[room]:
            for notification in notification_cache[room]:
                emit('notification', notification)
                
        emit('room_joined', {
            'room': room,
            'table_id': table_id
        })
    except Exception as e:
        logger.error(f"Error joining table room: {str(e)}")
        emit('error', {'message': str(e)})

# ===== Notification Functions =====
def notify_restaurant_new_order(order):
    """Notify restaurant about a new order."""
    try:
        # Basic validation
        if not order or not hasattr(order, 'id') or not hasattr(order, 'user_id'):
            current_app.logger.error("Invalid order object for socket notification")
            return False
            
        # Get table info
        table_id = order.table_id
        table_number = "Unknown"
        
        if order.assigned_table and hasattr(order.assigned_table, 'number'):
            table_number = order.assigned_table.number
            
        # Prepare order data
        order_data = {
            'id': order.id,
            'table_id': table_id,
            'table_number': table_number,
            'created_at': order.created_at.isoformat(),
            'status': order.status,
            'total_items': sum(item.quantity for item in order.items) if hasattr(order, 'items') else 0,
            'total_amount': float(order.final_amount) if hasattr(order, 'final_amount') and order.final_amount else 0
        }
        
        # Emit to restaurant room
        socketio.emit('new_order', {
            'order': order_data
        }, room=f"restaurant_{order.user_id}")
        
        # Log the notification
        current_app.logger.info(f"Socket notification sent: New order #{order.id} to restaurant #{order.user_id}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error sending socket notification for new order: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return False

def notify_customer_order_status(order, new_status, old_status):
    """Notify customer table about an order status change."""
    try:
        # Basic validation
        if not order or not hasattr(order, 'id') or not hasattr(order, 'table_id'):
            current_app.logger.error("Invalid order object for customer notification")
            return False
            
        # Get table info
        table_id = order.table_id
        table_number = "Unknown"
        
        if order.assigned_table and hasattr(order.assigned_table, 'number'):
            table_number = order.assigned_table.number
        
        # Get message based on status
        status_messages = {
            'pending': 'Your order has been received and is pending',
            'preparing': 'Your order is now being prepared',
            'ready': 'Your order is ready! Please collect from the counter',
            'completed': 'Your order has been completed. Thank you!',
            'cancelled': 'Your order has been cancelled'
        }
        
        message = status_messages.get(new_status, f'Your order status is now: {new_status}')
        
        # Determine notification type
        notification_type = 'info'
        if new_status == 'ready':
            notification_type = 'success'
        elif new_status == 'cancelled':
            notification_type = 'danger'
        
        # Emit to table room
        socketio.emit('notification', {
            'title': f'Order #{order.id} Update',
            'message': message,
            'type': notification_type,
            'order_id': order.id,
            'status': new_status
        }, room=f"table_{table_id}")
        
        # Log the notification
        current_app.logger.info(f"Socket notification sent to table #{table_number}: Order #{order.id} status = {new_status}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error sending customer notification for order status: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return False

def notify_restaurant_order_status(order, new_status, old_status):
    """Notify restaurant about an order status change."""
    try:
        # Basic validation
        if not order or not hasattr(order, 'id') or not hasattr(order, 'user_id'):
            current_app.logger.error("Invalid order object for socket notification")
            return False
            
        # Get table info
        table_id = order.table_id
        table_number = "Unknown"
        
        if order.assigned_table and hasattr(order.assigned_table, 'number'):
            table_number = order.assigned_table.number
            
        # Prepare status update data
        update_data = {
            'id': order.id,
            'table_id': table_id,
            'table_number': table_number,
            'status': new_status,
            'previous_status': old_status,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Emit to restaurant room
        socketio.emit('order_update', {
            'type': 'status_change',
            'order': update_data
        }, room=f"restaurant_{order.user_id}")
        
        # Log the notification
        current_app.logger.info(f"Socket notification sent: Order #{order.id} status change to {new_status}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error sending socket notification for order status update: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return False

# ===== API Routes =====
@notification_bp.route('/debug', methods=['GET'])
def debug_view():
    """Debug view to test notifications."""
    return render_template('notifications/debug.html')

@notification_bp.route('/test', methods=['POST'])
def test_notification():
    """Test notification endpoint."""
    try:
        data = request.json
        notification_type = data.get('type', 'test')
        room = data.get('room')
        
        if not room:
            return jsonify({'success': False, 'message': 'Room name is required'}), 400
            
        notification = {
            'type': notification_type,
            'title': data.get('title', 'Test Notification'),
            'message': data.get('message', 'This is a test notification'),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        socketio.emit('notification', notification, room=room)
        
        # Play sound if specified
        sound = data.get('sound')
        if sound:
            socketio.emit('play_sound', {'sound': sound}, room=room)
            
        return jsonify({'success': True, 'message': f'Test notification sent to {room}'})
    except Exception as e:
        logger.error(f"Error sending test notification: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500 