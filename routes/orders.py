from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, flash
from flask_login import login_required, current_user
from models import Order, OrderItem, MenuItem, Table, Feedback, db, User
from datetime import datetime
import json
import re
from extensions import socketio

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
    
@orders.route('/create', methods=['POST'])
def create_order():
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Check if table exists
    table_id = data.get('table_id')
    table = Table.query.get(table_id)
    if not table:
        return jsonify({'error': 'Table not found'}), 404
    
    # Get current user
    current_user = User.query.get(session.get('user_id'))
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401
    
    # Create order
    order = Order(
        user_id=current_user.id,
        table_id=table_id,
        payment_method=data.get('payment_method', 'later'),
        special_instructions=data.get('special_instructions', ''),
        customer_name=data.get('customer_name', ''),
        customer_phone=data.get('customer_phone', '')
    )
    
    db.session.add(order)
    db.session.flush()  # Get order ID
    
    # Add order items
    items = data.get('items', [])
    total_amount = 0
    
    for item_data in items:
        menu_item = MenuItem.query.get(item_data.get('id'))
        if not menu_item:
            continue
        
        quantity = item_data.get('quantity', 1)
        price = menu_item.price
        subtotal = price * quantity
        total_amount += subtotal
        
        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=menu_item.id,
            quantity=quantity,
            price=price,
            subtotal=subtotal
        )
        db.session.add(order_item)
    
    # Calculate totals
    order.total_amount = total_amount
    order.tax_amount = total_amount * 0.1  # 10% tax
    order.final_amount = order.total_amount + order.tax_amount
    
    # Process payment if payment method is 'now'
    if order.payment_method == 'now':
        # Payment processing logic would go here
        # For demo, we'll just mark it as paid
        order.payment_status = 'paid'
    
    db.session.commit()
    
    # Generate receipt URL
    receipt_url = url_for('orders.order_receipt', order_id=order.id, _external=True)
    
    flash('Order created successfully!', 'success')
    return jsonify({
        'success': True,
        'order_id': order.id,
        'receipt_url': receipt_url
    }), 201

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
        
    # Save the order to the database
    db.session.commit()
    
    # Log the status update
    current_app.logger.info(f"Order #{order.id} status updated from '{old_status}' to '{new_status}'")
    
    # Send notifications via Socket.IO
    try:
        # Import notification functions
        from routes.socket_notifications import notify_restaurant_order_status, notify_customer_order_status
        
        # Notify restaurant about status change
        notify_restaurant_order_status(order, new_status, old_status)
        
        # Notify customer about status change
        notify_customer_order_status(order, new_status, old_status)
    except Exception as notification_error:
        current_app.logger.error(f"Error sending notification for status update: {notification_error}")
    
    return jsonify({
        'success': True, 
        'message': f'Order status updated to {new_status}',
        'order_id': order.id,
        'status': new_status
    })

@orders.route('/api/active-orders')
@login_required
def get_active_orders():
    """Get active orders for the restaurant."""
    try:
        # Query active orders
        active_orders = Order.query.filter(
            Order.user_id == current_user.id,
            Order.status.in_(['pending', 'preparing', 'ready'])
        ).order_by(Order.created_at.desc()).all()
        
        # Format orders for JSON response
        orders_data = []
        for order in active_orders:
            # Get table number
            table_number = "Unknown"
            if order.table:
                table_number = order.table.number
                
            # Format order items
            items = []
            for item in order.items:
                menu_item_name = "Unknown"
                if item.menu_item:
                    menu_item_name = item.menu_item.name
                    
                items.append({
                    'id': item.id,
                    'name': menu_item_name,
                    'quantity': item.quantity,
                    'unit_price': float(item.unit_price)
                })
                
            # Add order to response
            orders_data.append({
                'id': order.id,
                'table_id': order.table_id,
                'table_number': table_number,
                'status': order.status,
                'customer_phone': order.customer_phone,
                'payment_method': order.payment_method,
                'payment_status': order.payment_status,
                'special_instructions': order.special_instructions,
                'items': items,
                'total_amount': float(order.total_amount) if order.total_amount else 0,
                'tax_amount': float(order.tax_amount) if order.tax_amount else 0,
                'final_amount': float(order.final_amount) if order.final_amount else 0,
                'created_at': order.created_at.isoformat(),
                'updated_at': order.updated_at.isoformat()
            })
            
        return jsonify({
            'success': True,
            'orders': orders_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting active orders: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

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
    """Generate a URL for the order receipt."""
    order = Order.query.get(order_id)
    if not order:
        current_app.logger.error(f"Unable to generate receipt: Order {order_id} not found")
        return None
    
    receipt_url = url_for('orders.order_receipt', order_id=order_id, _external=True)
    current_app.logger.info(f"Generated receipt URL for order {order_id}: {receipt_url}")
    return receipt_url

@orders.route('/api/orders/history')
def get_table_order_history():
    """Get order history for a specific table."""
    try:
        table_id = request.args.get('table_id')
        if not table_id or table_id == 'undefined' or table_id == 'null':
            return jsonify({'success': False, 'message': 'Valid Table ID is required'}), 400
            
        # Convert to integer if possible
        try:
            table_id = int(table_id)
        except ValueError:
            return jsonify({'success': False, 'message': 'Table ID must be a number'}), 400
            
        # Query orders for this table
        orders = Order.query.filter_by(
            table_id=table_id
        ).order_by(Order.created_at.desc()).all()
        
        orders_data = []
        for order in orders:
            items = []
            
            for item in order.items:
                menu_item = MenuItem.query.get(item.menu_item_id)
                item_name = "Unknown"
                if menu_item:
                    item_name = menu_item.name
                
                items.append({
                    'id': item.id,
                    'name': item_name,
                    'quantity': item.quantity,
                    'price': float(item.unit_price)
                })
            
            orders_data.append({
                'id': order.id,
                'table_id': order.table_id,
                'status': order.status,
                'created_at': order.created_at.isoformat(),
                'updated_at': order.updated_at.isoformat() if order.updated_at else order.created_at.isoformat(),
                'completed_at': order.completed_at.isoformat() if order.completed_at else None,
                'total_amount': float(order.total_amount) if order.total_amount else 0,
                'tax_amount': float(order.tax_amount) if order.tax_amount else 0,
                'final_amount': float(order.final_amount) if order.final_amount else 0,
                'items': items
            })
        
        return jsonify({
            'success': True,
            'orders': orders_data
        })
    
    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        current_app.logger.error(f"Error fetching table order history: {str(e)}\n{traceback_str}")
        return jsonify({'success': False, 'message': str(e)}), 500

@orders.route('/order/<int:order_id>/receipt')
def order_receipt(order_id):
    """Generate a receipt for an order"""
    # Get the order
    order = Order.query.get_or_404(order_id)
    
    # Get the restaurant information
    restaurant = User.query.get(order.user_id)
    
    # Prepare items list - ensure it's an iterable
    if hasattr(order, 'items') and callable(getattr(order, 'items')):
        # If items is a callable (like a query method)
        items_list = list(order.items)
    else:
        # If items is a direct property
        items_list = order.items if order.items else []
    
    # Calculate tax rate
    tax_rate = 10  # Default 10%
    if order.total_amount and order.total_amount > 0:
        tax_percentage = (order.tax_amount / order.total_amount) * 100
        tax_rate = round(tax_percentage, 1)
    
    # Get currency symbol from restaurant settings
    currency_symbol = '$'  # Default
    if hasattr(restaurant, 'currency_symbol') and restaurant.currency_symbol:
        currency_symbol = restaurant.currency_symbol
    
    # Render the receipt template
    return render_template('orders/receipt.html', 
                          order=order, 
                          restaurant=restaurant,
                          items_list=items_list,
                          currency_symbol=currency_symbol,
                          tax_rate=tax_rate)

@orders.route('/api/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    """Cancel an order."""
    try:
        order = Order.query.get_or_404(order_id)
        
        # Ensure the order belongs to the current user
        if order.user_id != current_user.id:
            return jsonify({
                'success': False,
                'message': 'Unauthorized'
            }), 403
        
        # Update order status
        order.status = 'cancelled'
        order.updated_at = datetime.utcnow()
        
        # Save changes
        db.session.commit()
        
        # Log the cancellation
        current_app.logger.info(f"Order #{order.id} cancelled by restaurant")
        
        # Notify restaurant and customer about the cancellation
        socketio.emit('order_update', {
            'type': 'status_change',
            'order': {
                'id': order.id,
                'status': order.status,
                'table_id': order.table_id
            },
            'previous_status': 'active'
        }, room=f"restaurant_{order.user_id}")
        
        # Send notification to table
        socketio.emit('notification', {
            'title': 'Order Cancelled',
            'message': f'Your order #{order.id} has been cancelled by the restaurant.',
            'type': 'warning'
        }, room=f"table_{order.table_id}")
        
        return jsonify({
            'success': True,
            'message': 'Order cancelled successfully',
            'order_id': order.id,
            'status': order.status
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback_str = traceback.format_exc()
        current_app.logger.error(f"Error cancelling order: {str(e)}\n{traceback_str}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500 

@orders.route('/restaurant/orders/receipts')
@login_required
def all_restaurant_receipts():
    """Display all receipts for a restaurant."""
    try:
        # Get all orders for this restaurant that are not cancelled
        orders = Order.query.filter_by(user_id=current_user.id).filter(Order.status != 'cancelled').order_by(Order.created_at.desc()).all()
        
        # Prepare data for template
        orders_data = []
        
        for order in orders:
            # Get table
            table = Table.query.get(order.table_id)
            table_number = "Unknown"
            if table:
                table_number = table.number
            
            # Get total items
            total_items = 0
            for item in order.items:
                total_items += item.quantity
            
            orders_data.append({
                'id': order.id,
                'table_number': table_number,
                'status': order.status,
                'created_at': order.created_at,
                'payment_method': order.payment_method if hasattr(order, 'payment_method') else 'unknown',
                'payment_status': order.payment_status if hasattr(order, 'payment_status') else 'unknown',
                'total_amount': float(order.total_amount) if order.total_amount else 0,
                'tax_amount': float(order.tax_amount) if order.tax_amount else 0,
                'final_amount': float(order.final_amount) if order.final_amount else 0,
                'total_items': total_items,
                'receipt_url': url_for('orders.order_receipt', order_id=order.id)
            })
        
        # Render template
        return render_template('orders/all_receipts.html', orders=orders_data)
        
    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        current_app.logger.error(f"Error displaying all receipts: {str(e)}\n{traceback_str}")
        flash('Error loading receipts', 'danger')
        return redirect(url_for('main.index')) 