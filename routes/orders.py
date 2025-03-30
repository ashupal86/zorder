from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from models import Order, OrderItem, MenuItem, Table, Feedback, db
from datetime import datetime
import json

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/orders/create', methods=['POST'])
def create_order():
    try:
        data = request.json
        
        # Validate required fields
        if not all(key in data for key in ['table_id', 'customer_phone', 'items']):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
            
        # Get the table and validate it exists
        table = Table.query.get_or_404(data['table_id'])
        
        # Create the order
        order = Order(
            table_id=table.id,
            user_id=table.user_id,  # Restaurant owner's ID
            customer_phone=data['customer_phone'],
            status='pending',
            payment_method=data['payment_method'],
            special_instructions=data.get('special_instructions', ''),
            created_at=datetime.utcnow()
        )
        
        db.session.add(order)
        
        # Add order items
        total_amount = 0
        for item_data in data['items']:
            menu_item = MenuItem.query.get_or_404(item_data['menu_item_id'])
            
            # Validate the menu item belongs to the restaurant
            if menu_item.user_id != table.user_id:
                return jsonify({
                    'success': False,
                    'message': 'Invalid menu item'
                }), 400
            
            order_item = OrderItem(
                order=order,
                menu_item=menu_item,
                quantity=item_data['quantity'],
                unit_price=menu_item.price,
                special_instructions=item_data.get('special_instructions', '')
            )
            
            total_amount += order_item.unit_price * order_item.quantity
            db.session.add(order_item)
        
        # Update order total
        order.total_amount = total_amount
        order.tax_amount = total_amount * 0.1  # 10% tax
        order.final_amount = total_amount + order.tax_amount
        
        db.session.commit()
        
        # TODO: Send notification to restaurant owner
        # TODO: Send confirmation SMS to customer
        
        return jsonify({
            'success': True,
            'message': 'Order created successfully',
            'order_id': order.id
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating order: {e}")
        return jsonify({
            'success': False,
            'message': 'Error creating order'
        }), 500

@orders_bp.route('/orders/active')
def get_active_orders():
    try:
        # Get all active orders for the restaurant
        active_orders = Order.query.filter(
            Order.user_id == current_user.id,
            Order.status.in_(['pending', 'preparing', 'ready'])
        ).order_by(Order.created_at.desc()).all()
        
        orders_data = []
        for order in active_orders:
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
            
            orders_data.append({
                'id': order.id,
                'table_number': order.table.number,
                'status': order.status,
                'customer_phone': order.customer_phone,
                'payment_method': order.payment_method,
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'total_amount': float(order.total_amount),
                'tax_amount': float(order.tax_amount),
                'final_amount': float(order.final_amount),
                'special_instructions': order.special_instructions,
                'items': order_items
            })
        
        return jsonify({
            'success': True,
            'orders': orders_data
        })
        
    except Exception as e:
        print(f"Error fetching active orders: {e}")
        return jsonify({
            'success': False,
            'message': 'Error fetching orders'
        }), 500

@orders_bp.route('/orders/history')
@login_required
def get_order_history():
    try:
        completed_orders = Order.query.filter(
            Order.user_id == current_user.id,
            Order.status.in_(['completed', 'cancelled'])
        ).order_by(Order.completed_at.desc()).all()
        
        orders_data = []
        for order in completed_orders:
            items = []
            for item in order.items:
                menu_item = MenuItem.query.get(item.menu_item_id)
                items.append({
                    'name': menu_item.name,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price
                })
            
            orders_data.append({
                'id': order.id,
                'table_number': order.table_number,
                'status': order.status,
                'total_amount': order.total_amount,
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'completed_at': order.completed_at.strftime('%Y-%m-%d %H:%M:%S') if order.completed_at else None,
                'items': items
            })
        
        return jsonify({'success': True, 'orders': orders_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@orders_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    try:
        data = request.json
        if 'status' not in data:
            return jsonify({
                'success': False,
                'message': 'Status is required'
            }), 400
            
        order = Order.query.get_or_404(order_id)
        
        # Validate the order belongs to the restaurant
        if order.user_id != current_user.id:
            return jsonify({
                'success': False,
                'message': 'Unauthorized'
            }), 403
            
        order.status = data['status']
        db.session.commit()
        
        # TODO: Send notification to customer about status update
        
        return jsonify({
            'success': True,
            'message': 'Order status updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating order status: {e}")
        return jsonify({
            'success': False,
            'message': 'Error updating order status'
        }), 500

@orders_bp.route('/order/<int:order_id>/pay', methods=['POST'])
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

@orders_bp.route('/order/<int:order_id>/feedback', methods=['POST'])
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