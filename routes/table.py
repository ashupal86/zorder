from flask import Blueprint, render_template, request, jsonify, send_file, current_app, url_for, flash
from flask_login import login_required, current_user
import qrcode
from io import BytesIO
import os
from models import Table, db, User, Order
from PIL import Image
from datetime import datetime
import socket
from urllib.parse import quote
from routes.orders import slugify

table_bp = Blueprint('table', __name__, url_prefix='/table')

# Add a root-level tables endpoint for compatibility
@table_bp.route('/tables', methods=['POST'])
@login_required
def add_table_root():
    """Compatibility route for creating tables at /tables"""
    # Check if we have form data or JSON data
    if request.is_json:
        # For JSON request (from JavaScript fetch)
        data = request.json
        
        # Create form-like object to pass to add_table
        class FormData:
            def __init__(self, data):
                self.data = data
            
            def get(self, key, default=None):
                return self.data.get(key, default)
        
        # Save original request.form
        original_form = request.form
        
        # Replace request.form with our JSON data
        request.form = FormData(data)
        
        # Call the actual handler
        result = add_table()
        
        # Restore original request.form
        request.form = original_form
        
        return result
    else:
        # For form data (from HTML form)
        return add_table()

@table_bp.route('/')
@login_required
def table_list():
    # Query all tables for this user, excluding those marked as "deleted"
    tables = Table.query.filter_by(user_id=current_user.id).filter(Table.status != 'deleted').order_by(Table.number).all()
    return render_template('table/list.html', tables=tables)

def generate_qr_code(table, restaurant_name):
    """Generate QR code for a table."""
    # Ensure we have valid data
    if not table or not table.id:
        return None
        
    # Create upload directory if it doesn't exist
    qr_dir = os.path.join(current_app.static_folder, 'qr_codes')
    if not os.path.exists(qr_dir):
        os.makedirs(qr_dir)
    
    # Create slugified restaurant name
    restaurant_slug = slugify(restaurant_name)
    
    # Generate a timestamp for uniqueness
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Generate the QR code filename - replace spaces with underscores for URLs
    safe_restaurant_name = restaurant_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
    filename = f"{safe_restaurant_name}_{table.number}_{timestamp}.png"
    qr_path = os.path.join(qr_dir, filename)
    
    # Generate absolute file path
    abs_path = os.path.abspath(qr_path)
    
    # Create the URL for the menu view with restaurant slug
    url = f"http://{request.host}/menu/{restaurant_slug}/view/{table.id}"
    current_app.logger.info(f"Creating QR code with URL: {url}")
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    # Create and save QR code image
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(abs_path)
    
    # Return path relative to static folder using forward slashes
    qr_code_path = f"qr_codes/{filename}"
    current_app.logger.info(f"Generated QR code at path: {qr_code_path}")
    return qr_code_path

@table_bp.route('/add', methods=['POST'])
@login_required
def add_table():
    """Add a new table to the current user's restaurant."""
    data = request.form
    
    # Validate table number
    try:
        table_number = int(data.get('number'))
        if table_number <= 0:
            return jsonify({'success': False, 'message': 'Table number must be positive'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid table number'}), 400
    
    # Validate capacity
    try:
        capacity = int(data.get('capacity', 4))
        if capacity <= 0:
            capacity = 4  # Default capacity
    except (ValueError, TypeError):
        capacity = 4  # Default capacity
    
    # Check if table number already exists for this restaurant
    existing_table = Table.query.filter_by(user_id=current_user.id, number=table_number).first()
    if existing_table:
        return jsonify({'success': False, 'message': 'Table number already exists'}), 400
    
    # Create new table
    table = Table(
        user_id=current_user.id,
        number=table_number,
        capacity=capacity,
        status='available'
    )
    
    # Add to database
    db.session.add(table)
    db.session.commit()
    
    # Generate QR code for the table
    restaurant_name = current_user.restaurant_name or current_user.name
    qr_code_path = generate_qr_code(table, restaurant_name)
    
    # Update table with QR code path
    table.qr_code = qr_code_path
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Table added successfully',
        'table': {
            'id': table.id,
            'number': table.number,
            'capacity': table.capacity,
            'status': table.status,
            'qr_code': url_for('static', filename=qr_code_path) if qr_code_path else None
        }
    })

@table_bp.route('/update/<int:id>', methods=['PUT'])
@login_required
def update_table(id):
    """Update an existing table."""
    table = Table.query.get_or_404(id)
    
    # Ensure the table belongs to the current user
    if table.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 403
        
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    try:
        # Check if new table number conflicts with existing ones
        if 'number' in data and data['number'] != table.number:
            existing_table = Table.query.filter_by(number=data['number'], user_id=current_user.id).first()
            if existing_table:
                return jsonify({'success': False, 'message': 'Table number already exists'}), 400
            
            # Update table number and regenerate QR code
            table.number = data['number']
            qr_code_path = generate_qr_code(table, current_user.restaurant_name or current_user.name)
            table.qr_code = qr_code_path
        
        # Update capacity if provided
        if 'capacity' in data:
            table.capacity = data['capacity']
        
        db.session.commit()
        flash('Table updated successfully', 'success')
        return jsonify({'success': True}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@table_bp.route('/delete/<int:id>', methods=['DELETE'])
@login_required
def delete_table(id):
    """Delete a table."""
    table = Table.query.get_or_404(id)
    
    # Ensure the table belongs to the current user
    if table.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 403
    
    try:
        # Check if there are any active orders for this table
        active_orders = Order.query.filter_by(
            table_id=table.id
        ).filter(
            Order.status.in_(['pending', 'preparing', 'ready'])
        ).count()
        
        if active_orders > 0:
            return jsonify({
                'success': False, 
                'message': f'Cannot delete table with active orders. Please complete or cancel all orders first.'
            }), 400
            
        # Delete QR code file if it exists
        if table.qr_code:
            qr_path = table.qr_code
            # Ensure we have a clean path relative to static folder
            if qr_path.startswith('/'):
                qr_path = qr_path[1:]
            if qr_path.startswith('static/'):
                qr_path = qr_path[7:]  # Remove 'static/' prefix if present
                
            # Normalize the path for the OS
            qr_file = os.path.join(current_app.static_folder, qr_path)
            current_app.logger.info(f"Attempting to delete QR code at: {qr_file}")
            
            if os.path.exists(qr_file):
                os.remove(qr_file)
                current_app.logger.info(f"Successfully deleted QR code file: {qr_file}")
            else:
                current_app.logger.warning(f"QR code file not found at: {qr_file}")
        
        # Instead of deleting table, mark it as archived/deleted
        table.status = 'deleted'
        table.qr_code = None  # Remove QR code reference
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Table deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting table: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@table_bp.route('/qr/<int:id>')
@login_required
def get_qr(id):
    """Generate or regenerate QR code for a table."""
    try:
        table = Table.query.get_or_404(id)
        
        # Ensure the table belongs to the current user
        if table.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Unauthorized access'}), 403
        
        # Get restaurant information
        restaurant = User.query.get_or_404(table.user_id)
        restaurant_name = restaurant.restaurant_name or restaurant.name
        
        # Delete old QR code if it exists
        if table.qr_code:
            qr_path = table.qr_code
            # Ensure we have a clean path relative to static folder
            if qr_path.startswith('/'):
                qr_path = qr_path[1:]
            if qr_path.startswith('static/'):
                qr_path = qr_path[7:]  # Remove 'static/' prefix if present
                
            # Normalize the path for the OS
            old_qr_file = os.path.join(current_app.static_folder, qr_path)
            current_app.logger.info(f"Attempting to delete old QR code at: {old_qr_file}")
            
            if os.path.exists(old_qr_file):
                try:
                    os.remove(old_qr_file)
                    current_app.logger.info(f"Successfully deleted old QR code: {old_qr_file}")
                except Exception as e:
                    current_app.logger.warning(f"Could not delete old QR code: {e}")
            else:
                current_app.logger.warning(f"Old QR code file not found at: {old_qr_file}")
        
        # Generate new QR code
        qr_code_path = generate_qr_code(table, restaurant_name)
        
        if not qr_code_path:
            return jsonify({'success': False, 'message': 'Failed to generate QR code'}), 500
            
        table.qr_code = qr_code_path
        db.session.commit()
        
        # Get the full URL for the menu
        menu_url = url_for('menu.view_menu', restaurant_slug=slugify(restaurant_name), table_id=table.id, _external=True)
        
        current_app.logger.info(f"QR code regenerated for table {table.number}: {qr_code_path}")
        
        return jsonify({
            'success': True, 
            'qr_code': url_for('static', filename=qr_code_path),
            'restaurant_name': restaurant_name,
            'table_number': table.number,
            'menu_url': menu_url
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error generating QR code: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@table_bp.route('/list')
@login_required
def list_tables():
    """List all tables."""
    tables = Table.query.order_by(Table.number).all()
    return render_template('table/list.html', tables=tables)

def get_next_table_number(user_id):
    """Get the next available table number for this restaurant."""
    # Find the highest current table number
    highest_table = Table.query.filter_by(user_id=user_id).order_by(Table.number.desc()).first()
    
    # Start with table number 1 if no tables exist, otherwise increment by 1
    if highest_table:
        return highest_table.number + 1
    else:
        return 1

@table_bp.route('/auto-add', methods=['POST'])
@login_required
def auto_add_table():
    """Add a new table automatically with sequential numbering."""
    try:
        # Get next available table number
        table_number = get_next_table_number(current_user.id)
        
        # Default capacity
        capacity = 4
        
        # Check if table number already exists for this restaurant (shouldn't happen, but just in case)
        existing_table = Table.query.filter_by(user_id=current_user.id, number=table_number).first()
        if existing_table:
            return jsonify({'success': False, 'message': f'Table {table_number} already exists'}), 400
        
        # Create new table
        table = Table(
            user_id=current_user.id,
            number=table_number,
            capacity=capacity,
            status='available'
        )
        
        # Add to database
        db.session.add(table)
        db.session.commit()
        
        # Generate QR code for the table
        restaurant_name = current_user.restaurant_name or current_user.name
        qr_code_path = generate_qr_code(table, restaurant_name)
        
        # Update table with QR code path
        table.qr_code = qr_code_path
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Table {table_number} added successfully',
            'table': {
                'id': table.id,
                'number': table.number,
                'capacity': table.capacity,
                'status': table.status,
                'qr_code': url_for('static', filename=qr_code_path) if qr_code_path else None
            }
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error auto-adding table: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500 