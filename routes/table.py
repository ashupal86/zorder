from flask import Blueprint, render_template, request, jsonify, send_file, current_app, url_for, flash
from flask_login import login_required, current_user
import qrcode
from io import BytesIO
import os
from models import Table, db
from PIL import Image
from datetime import datetime
import socket

table_bp = Blueprint('table', __name__, url_prefix='/table')

@table_bp.route('/')
@login_required
def table_list():
    tables = Table.query.filter_by(user_id=current_user.id).order_by(Table.number).all()
    return render_template('table/list.html', tables=tables)

def generate_qr_code(table_id, table_number):
    """Generate a QR code for a table and save it to the static folder."""
    try:
        # Get the table
        table = Table.query.get_or_404(table_id)
        
        # Get restaurant info
        from models import User
        restaurant = User.query.get_or_404(table.user_id)
        restaurant_name = restaurant.restaurant_name or restaurant.name
        safe_restaurant_name = ''.join(c for c in restaurant_name if c.isalnum() or c.isspace()).strip().replace(' ', '_')
        
        # Create QR code instance
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Create the menu URL with table_id for the QR code
        # Use Flask's url_for with _external=True to get the fully qualified URL
        menu_url = url_for('menu.view_menu', table_id=table_id, _external=True)
        
        # Add data to QR code
        qr.add_data(menu_url)
        qr.make(fit=True)

        # Create QR code image
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Create directory if it doesn't exist
        qr_dir = os.path.join(current_app.static_folder, 'qr_codes')
        os.makedirs(qr_dir, exist_ok=True)
        
        # Save QR code image with restaurant name and table number
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{safe_restaurant_name}_table_{table_number}_{timestamp}.png"
        file_path = os.path.join(qr_dir, filename)
        qr_image.save(file_path)
        
        # Return the URL path for the QR code
        return f"/static/qr_codes/{filename}"
    except Exception as e:
        current_app.logger.error(f"Error generating QR code: {e}")
        return None

@table_bp.route('/add', methods=['POST'])
@login_required
def add_table():
    """Add a new table."""
    data = request.get_json()
    
    if not data or 'number' not in data or 'capacity' not in data:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    # Check if table number already exists for this user
    existing_table = Table.query.filter_by(number=data['number'], user_id=current_user.id).first()
    if existing_table:
        return jsonify({'success': False, 'message': 'Table number already exists'}), 400
    
    try:
        # Create new table
        table = Table(
            number=data['number'],
            capacity=data['capacity'],
            is_occupied=False,
            user_id=current_user.id
        )
        db.session.add(table)
        db.session.flush()  # Get the table ID before commit
        
        # Generate QR code
        qr_code_url = generate_qr_code(table.id, table.number)
        table.qr_code = qr_code_url
        
        db.session.commit()
        flash('Table added successfully', 'success')
        return jsonify({'success': True, 'id': table.id}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

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
            qr_code_url = generate_qr_code(table.id, table.number)
            table.qr_code = qr_code_url
        
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
        # Delete QR code file if it exists
        if table.qr_code:
            qr_file = os.path.join(current_app.static_folder, table.qr_code.lstrip('/static/'))
            if os.path.exists(qr_file):
                os.remove(qr_file)
        
        db.session.delete(table)
        db.session.commit()
        flash('Table deleted successfully', 'success')
        return jsonify({'success': True}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@table_bp.route('/toggle/<int:id>', methods=['PUT'])
@login_required
def toggle_table(id):
    """Toggle table occupied status."""
    table = Table.query.get_or_404(id)
    
    # Ensure the table belongs to the current user
    if table.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 403
    
    try:
        table.is_occupied = not table.is_occupied
        db.session.commit()
        status = 'occupied' if table.is_occupied else 'available'
        flash(f'Table marked as {status}', 'success')
        return jsonify({'success': True}), 200
        
    except Exception as e:
        db.session.rollback()
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
        from models import User
        restaurant = User.query.get_or_404(table.user_id)
        restaurant_name = restaurant.restaurant_name or restaurant.name
        
        # Delete old QR code if it exists
        if table.qr_code:
            old_qr_file = os.path.join(current_app.static_folder, table.qr_code.lstrip('/static/'))
            if os.path.exists(old_qr_file):
                try:
                    os.remove(old_qr_file)
                except Exception as e:
                    current_app.logger.warning(f"Could not delete old QR code: {e}")
        
        # Generate new QR code
        qr_code_url = generate_qr_code(table.id, table.number)
        
        if not qr_code_url:
            return jsonify({'success': False, 'message': 'Failed to generate QR code'}), 500
            
        table.qr_code = qr_code_url
        db.session.commit()
        
        # Get the full URL for the menu
        menu_url = url_for('menu.view_menu', table_id=table.id, _external=True)
        
        flash('QR code regenerated successfully', 'success')
        return jsonify({
            'success': True, 
            'qr_code': qr_code_url,
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