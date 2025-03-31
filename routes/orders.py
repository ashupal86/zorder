from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for
from flask_login import login_required, current_user
from models import Order, OrderItem, MenuItem, Table, Feedback, db, User
from datetime import datetime
import json
from routes.socket_notifications import notify_restaurant_new_order, notify_customer_order_status
import re

orders = Blueprint('orders', __name__)

def slugify(text):
    """Convert text to URL-friendly slug."""
    # Convert to lowercase and replace spaces with hyphens
    text = text.lower().replace(' ', '-')
    # Remove special characters
    text = re.sub(r'[^a-z0-9-]', '', text)
    # Remove multiple hyphens
    text = re.sub(r'-+', '-', text)
    return text

def get_restaurant_by_slug(slug):
    """Get restaurant by slug."""
    # First try direct ID match for backward compatibility
    try:
        restaurant_id = int(slug)
        return User.query.get(restaurant_id)
    except ValueError:
        pass
    
    # Then try to match by slugified name
    all_restaurants = User.query.all()
    for restaurant in all_restaurants:
        restaurant_name = restaurant.restaurant_name or restaurant.name
        if slugify(restaurant_name) == slug:
            return restaurant
    
    return None

@orders.route('/restaurant/<restaurant_slug>/orders')
@login_required
def orders_page(restaurant_slug):
    """Display all orders for the restaurant."""
    # Get restaurant by slug
    restaurant = get_restaurant_by_slug(restaurant_slug)
    if not restaurant:
        return jsonify({'success': False, 'message': 'Restaurant not found'}), 404
    
    # Check if user owns this restaurant
    if current_user.id != restaurant.id:
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 403
        
    active_orders = Order.query.filter(
        Order.user_id == restaurant.id,
        Order.status.in_(['pending', 'preparing', 'ready'])
    ).order_by(Order.created_at.desc()).all()
    
    completed_orders = Order.query.filter(
        Order.user_id == restaurant.id,
        Order.status == 'completed'
    ).order_by(Order.created_at.desc()).limit(10).all()
    
    restaurant_name = restaurant.restaurant_name or restaurant.name
    restaurant_slug = slugify(restaurant_name)
    
    return render_template(
        'orders.html', 
        active_orders=active_orders, 
        completed_orders=completed_orders,
        restaurant=restaurant,
        restaurant_id=restaurant.id,
        restaurant_name=restaurant_name,
        restaurant_slug=restaurant_slug
    )

@orders.route('/restaurant/<restaurant_slug>/menu')
@login_required
def restaurant_menu(restaurant_slug):
    """Display menu management for a restaurant."""
    # Get restaurant by slug
    restaurant = get_restaurant_by_slug(restaurant_slug)
    if not restaurant:
        return jsonify({'success': False, 'message': 'Restaurant not found'}), 404
    
    # Check if user owns this restaurant
    if current_user.id != restaurant.id:
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 403
        
    # Convert menu items to dictionary for JSON serialization
    menu_items = MenuItem.query.filter_by(user_id=restaurant.id).all()
    menu_items_json = [item.to_dict() for item in menu_items]
    
    restaurant_name = restaurant.restaurant_name or restaurant.name
    restaurant_slug = slugify(restaurant_name)
    
    return render_template(
        'menu/manage.html',
        menu_items=menu_items_json,
        restaurant=restaurant,
        restaurant_id=restaurant.id,
        restaurant_name=restaurant_name,
        restaurant_slug=restaurant_slug
    )

# Route for backward compatibility
@orders.route('/restaurant/<int:restaurant_id>/orders')
@login_required
def orders_page_by_id(restaurant_id):
    """Redirect to slug-based URL."""
    restaurant = User.query.get_or_404(restaurant_id)
    restaurant_name = restaurant.restaurant_name or restaurant.name
    restaurant_slug = slugify(restaurant_name)
    return redirect(url_for('orders.orders_page', restaurant_slug=restaurant_slug))

# Route for backward compatibility
@orders.route('/restaurant/<int:restaurant_id>/menu')
@login_required
def restaurant_menu_by_id(restaurant_id):
    """Redirect to slug-based URL."""
    restaurant = User.query.get_or_404(restaurant_id)
    restaurant_name = restaurant.restaurant_name or restaurant.name
    restaurant_slug = slugify(restaurant_name)
    return redirect(url_for('orders.restaurant_menu', restaurant_slug=restaurant_slug))
    
@orders.route('/api/orders', methods=['POST'])
def create_order():
    """Create a new order for a table."""
    data = request.json
    
    # Validate the request data
    if not data or 'table_id' not in data or 'items' not in data:
        return jsonify({'success': False, 'message': 'Invalid request data'}), 400
    
    # Check if the table exists
    table = Table.query.get(data['table_id'])
    if not table:
        return jsonify({'success': False, 'message': 'Table not found'}), 404
    
    # Create the order
    order = Order(
        table_id=table.id,
        user_id=table.user_id,
        status='pending',
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # Add order items
    for item_data in data['items']:
        menu_item = MenuItem.query.get(item_data['menu_item_id'])
        if not menu_item:
            return jsonify({'success': False, 'message': f'Menu item {item_data["menu_item_id"]} not found'}), 404
        
        order_item = OrderItem(
            menu_item_id=menu_item.id,
            quantity=item_data['quantity'],
            unit_price=menu_item.price
        )
        order.items.append(order_item)
    
    # Calculate total
    total = sum(item.unit_price * item.quantity for item in order.items)
    order.total_amount = total
    order.tax_amount = round(total * 0.08, 2)  # 8% tax
    order.final_amount = order.total_amount + order.tax_amount
    
    # Save the order to the database
    db.session.add(order)
    db.session.commit()
    
    # Send notification about new order
    try:
        notify_restaurant_new_order(order)
        current_app.logger.info(f"Socket.IO notification sent for new order #{order.id}")
    except Exception as e:
        current_app.logger.error(f"Error sending Socket.IO notification for new order #{order.id}: {e}")
    
    return jsonify({
        'success': True,
        'message': 'Order created successfully',
        'order_id': order.id
    })

@orders.route('/api/orders/<int:order_id>/status', methods=['PUT'])
@login_required
def update_order_status(order_id):
    """Update the status of an order."""
    data = request.json
    
    # Validate the request data
    if not data or 'status' not in data:
        return jsonify({'success': False, 'message': 'Status is required'}), 400
    
    # Get the order
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'success': False, 'message': 'Order not found'}), 404
    
    # Verify that the user owns the order
    if order.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Not authorized to update this order'}), 403
    
    new_status = data['status']
    
    # Validate status
    valid_statuses = ['pending', 'preparing', 'ready', 'completed', 'cancelled']
    if new_status not in valid_statuses:
        return jsonify({'success': False, 'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
    
    # Update the order status
    old_status = order.status
    order.status = new_status
    order.updated_at = datetime.utcnow()
    
    # Ensure table_id exists - this prevents integrity errors
    if not order.table_id:
        return jsonify({'success': False, 'message': 'Order has no table association'}), 400
    
    # Set completed_at timestamp when order is completed
    if new_status == 'completed' and not order.completed_at:
        order.completed_at = datetime.utcnow()
        
        # If total_amount is not set, calculate it from items
        if not order.total_amount or order.total_amount == 0:
            total = 0
            for item in order.items:
                total += item.unit_price * item.quantity
            order.total_amount = total
            
            # Set default tax and final amount if needed
            if not order.tax_amount:
                order.tax_amount = round(total * 0.08, 2)  # 8% tax as default
            if not order.final_amount:
                order.final_amount = order.total_amount + order.tax_amount
    
    try:
        db.session.commit()
        
        # Send notification to customer about order status update
        try:
            notify_customer_order_status(order, new_status)
            current_app.logger.info(f"Socket.IO notification sent for order #{order.id} status update to {new_status}")
        except Exception as e:
            current_app.logger.error(f"Error sending Socket.IO notification for order status update: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Order status updated to {new_status}',
            'order_id': order.id,
            'old_status': old_status,
            'new_status': new_status
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating order status: {e}")
        return jsonify({'success': False, 'message': f'Error updating order: {str(e)}'}), 500

@orders.route('/api/table/<int:table_id>/orders')
def get_table_orders(table_id):
    """Get all active orders for a table."""
    # Get active orders for the table
    active_orders = Order.query.filter(
        Order.table_id == table_id,
        Order.status.in_(['pending', 'preparing', 'ready'])
    ).order_by(Order.created_at.desc()).all()
    
    orders_data = []
    for order in active_orders:
        items_data = []
        for item in order.items:
            items_data.append({
                'id': item.id,
                'name': item.menu_item.name,
                'quantity': item.quantity,
                'price': float(item.price)
            })
        
        orders_data.append({
            'id': order.id,
            'status': order.status,
            'created_at': order.created_at.isoformat(),
            'updated_at': order.updated_at.isoformat() if hasattr(order, 'updated_at') and order.updated_at else None,
            'items': items_data
        })
    
    return jsonify({'success': True, 'orders': orders_data})

@orders.route('/api/restaurant/active-orders')
@login_required
def get_active_orders():
    """Get all active orders for the restaurant."""
    try:
        # Get all active orders for the restaurant
        active_orders = Order.query.filter(
            Order.user_id == current_user.id,
            Order.status.in_(['pending', 'preparing', 'ready'])
        ).order_by(Order.created_at.desc()).all()
        
        # Format orders for JSON response
        orders_data = []
        for order in active_orders:
            # Get order items data
            items_data = []
            for item in order.items:
                try:
                    menu_item = MenuItem.query.get(item.menu_item_id)
                    if menu_item:
                        items_data.append({
                            'id': item.id,
                            'name': menu_item.name,
                            'quantity': item.quantity,
                            'price': float(item.unit_price) if item.unit_price else 0.0
                        })
                except Exception as e:
                    current_app.logger.error(f"Error processing menu item: {str(e)}")
            
            # Get table information safely
            table_number = "Unknown"
            if order.table:
                try:
                    table_number = order.table.number
                except Exception as e:
                    current_app.logger.error(f"Error getting table number: {str(e)}")
            
            # Calculate total price safely
            try:
                total_amount = sum(item.unit_price * item.quantity for item in order.items if item.unit_price)
            except Exception as e:
                current_app.logger.error(f"Error calculating total amount: {str(e)}")
                total_amount = 0
            
            # Format order data
            try:
                order_data = {
                    'id': order.id,
                    'table_id': order.table_id,
                    'table_number': table_number,
                    'status': order.status,
                    'created_at': order.created_at.isoformat() if order.created_at else datetime.utcnow().isoformat(),
                    'updated_at': order.updated_at.isoformat() if order.updated_at else order.created_at.isoformat() if order.created_at else datetime.utcnow().isoformat(),
                    'total_amount': float(total_amount),
                    'items': items_data
                }
                orders_data.append(order_data)
                current_app.logger.info(f"Added order {order.id} to response data")
            except Exception as e:
                current_app.logger.error(f"Error formatting order data: {str(e)}")
        
        # Return success response
        current_app.logger.info(f"Returning {len(orders_data)} active orders")
        return jsonify({
            'success': True, 
            'orders': orders_data,
            'restaurant_id': current_user.id,
            'restaurant_name': current_user.restaurant_name or current_user.name
        })
    
    except Exception as e:
        # Log the error and return error response
        current_app.logger.error(f"Error fetching active orders: {str(e)}")
        return jsonify({
            'success': False, 
            'message': 'Failed to fetch active orders', 
            'error': str(e)
        }), 500

@orders.route('/restaurant/<restaurant_slug>/orders/history')
@login_required
def get_order_history(restaurant_slug):
    """Get order history for a specific restaurant."""
    # Get restaurant by slug
    restaurant = get_restaurant_by_slug(restaurant_slug)
    if not restaurant:
        return jsonify({'success': False, 'message': 'Restaurant not found'}), 404
    
    # Check if user owns this restaurant
    if current_user.id != restaurant.id:
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 403
        
    try:
        # Use updated_at or created_at for sorting instead of completed_at
        completed_orders = Order.query.filter(
            Order.user_id == restaurant.id,
            Order.status.in_(['completed', 'cancelled'])
        ).order_by(Order.updated_at.desc()).all()
        
        orders_data = []
        for order in completed_orders:
            total_amount = 0
            items = []
            
            for item in order.items:
                menu_item = MenuItem.query.get(item.menu_item_id)
                item_total = float(item.unit_price) * item.quantity
                total_amount += item_total
                
                items.append({
                    'id': item.id,
                    'name': menu_item.name,
                    'quantity': item.quantity,
                    'price': float(item.unit_price)
                })
            
            # Get table number
            table_number = order.table.number if order.table else 'Unknown'
            
            orders_data.append({
                'id': order.id,
                'table_id': order.table_id,
                'table_number': table_number,
                'status': order.status,
                'total_amount': total_amount,
                'created_at': order.created_at.isoformat(),
                'updated_at': order.updated_at.isoformat() if order.updated_at else order.created_at.isoformat(),
                'completed_at': order.completed_at.isoformat() if order.completed_at else order.updated_at.isoformat(),
                'items': items
            })
        
        return jsonify({'success': True, 'orders': orders_data})
    except Exception as e:
        current_app.logger.error(f"Error fetching order history: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@orders.route('/order/<int:order_id>/pay', methods=['POST'])
def process_payment(order_id):
    order = Order.query.get_or_404(order_id)
    data = request.json
    payment_method = data.get('payment_method')
    
    if order.payment_status == 'paid':
        return jsonify({'error': 'Order already paid'}), 400
    
    # Process payment (integrate with payment gateway here)
    # For demo, we'll just mark it as paid
    order.payment_status = 'paid'
    order.payment_method = payment_method
    order.status = 'paid'
    db.session.commit()
    
    return jsonify({
        'message': 'Payment processed successfully',
        'receipt_url': generate_receipt(order_id)
    })

@orders.route('/order/<int:order_id>/feedback', methods=['POST'])
def submit_feedback(order_id):
    data = request.json
    feedback = Feedback(
        order_id=order_id,
        rating=data.get('rating'),
        comment=data.get('comment', '')
    )
    db.session.add(feedback)
    db.session.commit()
    
    return jsonify({'message': 'Feedback submitted successfully'})

def estimate_preparation_time(order_id):
    order = Order.query.get(order_id)
    total_time = 0
    
    # Get current kitchen load
    active_orders = Order.query.filter(
        Order.status.in_(['pending', 'preparing'])
    ).count()
    
    # Calculate base preparation time from menu items
    for item in order.items:
        menu_item = MenuItem.query.get(item.menu_item_id)
        total_time += menu_item.preparation_time * item.quantity
    
    # Add overhead based on kitchen load
    load_factor = 1 + (active_orders * 0.1)  # 10% increase per active order
    estimated_time = total_time * load_factor
    
    return round(estimated_time)

def generate_receipt(order_id):
    order = Order.query.get(order_id)
    # Generate receipt logic here
    # For demo, we'll just return a dummy URL
    return f'/receipts/{order_id}.pdf'

# Add a new route for viewing a single order receipt
@orders.route('/order/<int:order_id>/receipt')
def order_receipt(order_id):
    try:
        order = Order.query.get_or_404(order_id)
        
        # Ensure the order belongs to the current user
        if order.user_id != current_user.id:
            return jsonify({
                'success': False,
                'message': 'Unauthorized'
            }), 403
            
        # Get restaurant name
        restaurant = User.query.get(order.user_id)
        
        # Prepare order data for the template
        order_items = []
        for item in order.items:
            order_items.append({
                'id': item.id,
                'name': item.menu_item.name,
                'quantity': item.quantity,
                'unit_price': float(item.unit_price),
                'total_price': float(item.unit_price * item.quantity),
                'special_instructions': item.special_instructions
            })
        
        order_data = {
            'id': order.id,
            'restaurant_name': restaurant.restaurant_name,
            'table_number': order.table.number,
            'status': order.status,
            'customer_phone': order.customer_phone,
            'payment_method': order.payment_method,
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': datetime.timestamp(order.created_at),
            'total_amount': float(order.total_amount),
            'tax_amount': float(order.tax_amount),
            'final_amount': float(order.final_amount),
            'special_instructions': order.special_instructions,
            'items': order_items
        }
        
        return render_template('orders/receipt.html', order=order_data)
        
    except Exception as e:
        print(f"Error generating receipt: {e}")
        return jsonify({
            'success': False,
            'message': 'Error generating receipt'
        }), 500 