import sys
import logging
import time
import threading
import json

# Set up logging to catch all console output
logging.basicConfig(level=logging.DEBUG)

def check_database():
    """Check the database for orders and their tables."""
    # Import here to avoid circular imports
    from app import app
    from models import Order, db, User, Table
    
    with app.app_context():
        app.logger.setLevel(logging.DEBUG)
        print("Checking database...")
        
        # Check all orders
        orders = Order.query.all()
        print(f"Found {len(orders)} orders in database")
        
        if orders:
            # Check the first few orders
            for order in orders[:3]:
                print(f"Order {order.id}: status={order.status}, table_id={order.table_id}")
                
                # Check if the order has a table
                if order.table_id:
                    table = Table.query.get(order.table_id)
                    if table:
                        print(f"  Table found: {table.id}, number={table.number}")
                    else:
                        print(f"  ERROR: Table {order.table_id} not found in database!")
                else:
                    print("  Order has no table_id")
        
        # Check all tables
        tables = Table.query.all()
        print(f"Found {len(tables)} tables in database")
        
        # Check all users (for restaurant subscriptions)
        users = User.query.all()
        print(f"Found {len(users)} users in database")

def check_socketio_state():
    """Check the status of Socket.IO connections and notification cache."""
    # Import here to avoid circular imports
    from app import app
    
    with app.app_context():
        try:
            # Import the Socket.IO structures from socket_notifications
            from routes.socket_notifications import connected_clients, customer_tables, notification_cache
            
            print("\nChecking Socket.IO state...")
            
            # Check connected clients
            print(f"Connected clients by table: {len(connected_clients)} tables")
            for table_id, clients in connected_clients.items():
                print(f"Table {table_id}: {len(clients)} connected clients")
                
            # Check customer tables mapping
            print(f"Customer-table mappings: {len(customer_tables)} customers")
            for customer_id, tables in customer_tables.items():
                print(f"Customer {customer_id}: associated with {len(tables)} tables: {', '.join(map(str, tables))}")
                
            # Check notification cache
            print(f"Notification cache: {len(notification_cache)} entries")
            for room, notifications in notification_cache.items():
                print(f"Room {room}: {len(notifications)} cached notifications")
                if notifications:
                    print(f"  First notification: {notifications[0]['title'] if 'title' in notifications[0] else 'Unknown'}")
                    
        except ImportError as e:
            print(f"Error importing Socket.IO structures: {e}")
            
def simulate_order_update():
    """Simulate updating an order to test notification triggers."""
    # Import here to avoid circular imports
    from app import app
    from models import Order, db, User, Table
    
    with app.app_context():
        # Get a pending order
        order = Order.query.filter_by(status='pending').first()
        
        if not order:
            print("No pending orders found. Creating a test order...")
            # Create a test order
            tables = Table.query.all()
            if not tables:
                print("ERROR: No tables found in database!")
                return
                
            table = tables[0]
            restaurant = User.query.first()  # Get the first restaurant user
            
            if not restaurant:
                print("ERROR: No restaurant users found in database!")
                return
                
            # Create new order
            order = Order(
                table_id=table.id,
                user_id=restaurant.id,
                status='pending',
                created_at=db.func.now(),
                updated_at=db.func.now()
            )
            
            db.session.add(order)
            db.session.commit()
            print(f"Created test order {order.id} for table {table.number}")
            
        print(f"Found order {order.id} with status {order.status}")
        
        # Check if order has a valid table
        if not order.table_id:
            print("Order has no table_id, notification won't work")
            return
            
        table = Table.query.get(order.table_id)
        if not table:
            print(f"Table {order.table_id} not found in database")
            return
            
        print(f"Order belongs to table {table.number}")
        
        # Update order status to trigger notification
        old_status = order.status
        order.status = 'preparing'
        order.updated_at = db.func.now()
        db.session.commit()
        
        print(f"Updated order {order.id} status from {old_status} to preparing")
        print("This should trigger a Socket.IO notification if clients are connected")
        
        # Wait a moment for the notification to be processed
        time.sleep(0.5)
        
        # Check Socket.IO state after update
        check_socketio_state()

# Main execution
if __name__ == "__main__":
    print("Starting database check...")
    check_database()
    
    print("\nChecking Socket.IO state...")
    check_socketio_state()
    
    print("\nSimulating order update...")
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        simulate_order_update()
    
    print("Done.") 