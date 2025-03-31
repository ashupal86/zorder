from flask import Flask
from models import Order, db
import sys
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestNotifications")

def update_order_status(app, order_id, new_status):
    """Update an order's status to trigger notification."""
    with app.app_context():
        try:
            order = Order.query.get(order_id)
            if not order:
                logger.error(f"Order {order_id} not found")
                return False
                
            old_status = order.status
            logger.info(f"Updating order {order_id} status: {old_status} -> {new_status}")
            
            order.status = new_status
            order.updated_at = datetime.utcnow()
            
            if new_status == 'completed':
                order.completed_at = datetime.utcnow()
                
            db.session.commit()
            logger.info(f"Order {order_id} status updated successfully")
            
            # Give time for notification to process
            time.sleep(1)
            
            return True
        except Exception as e:
            logger.error(f"Error updating order status: {str(e)}")
            db.session.rollback()
            return False

def simulate_order_status_flow(app, order_id):
    """Simulate a complete order flow from pending to completed."""
    logger.info(f"Starting status flow simulation for order {order_id}")
    
    # Update to preparing
    if update_order_status(app, order_id, 'preparing'):
        logger.info("Order marked as preparing")
    else:
        logger.error("Failed to update order to preparing status")
        return False
        
    # Wait 5 seconds
    time.sleep(5)
    
    # Update to ready
    if update_order_status(app, order_id, 'ready'):
        logger.info("Order marked as ready")
    else:
        logger.error("Failed to update order to ready status")
        return False
        
    # Wait 5 seconds
    time.sleep(5)
    
    # Update to completed
    if update_order_status(app, order_id, 'completed'):
        logger.info("Order marked as completed")
    else:
        logger.error("Failed to update order to completed status")
        return False
        
    logger.info("Order status flow simulation completed successfully")
    return True

if __name__ == "__main__":
    # Import app after the model to avoid circular imports
    from app import app
    
    if len(sys.argv) < 2:
        print("Usage: python test_notification.py [order_id]")
        sys.exit(1)
        
    try:
        order_id = int(sys.argv[1])
    except ValueError:
        print("Order ID must be a number")
        sys.exit(1)
        
    simulate_order_status_flow(app, order_id) 