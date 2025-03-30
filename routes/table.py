from flask import Blueprint, render_template, request, jsonify, send_file, current_app, url_for, flash
from flask_login import login_required, current_user
import qrcode
from io import BytesIO
import os
from models import Table, db
from PIL import Image
from datetime import datetime

table_bp = Blueprint('table', __name__, url_prefix='/table')

@table_bp.route('/')
@login_required
def table_list():
    tables = Table.query.filter_by(user_id=current_user.id).order_by(Table.number).all()
    return render_template('table/list.html', tables=tables)

def generate_qr_code(table_id, table_number):
    """Generate a QR code for a table and save it to the static folder."""
    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    
    # Get the base URL from config or use the server name
    server_name = current_app.config.get('SERVER_NAME', 'localhost:5001')
    scheme = current_app.config.get('PREFERRED_URL_SCHEME', 'http')
    base_url = f"{scheme}://{server_name}"
    
    # Add data to QR code
    menu_url = f"{base_url}/menu/view/{table_id}"
    qr.add_data(menu_url)
    qr.make(fit=True)

    # Create QR code image
    qr_image = qr.make_image(fill_color="black", back_color="white")
    
    # Create directory if it doesn't exist
    qr_dir = os.path.join(current_app.static_folder, 'qr_codes')
    os.makedirs(qr_dir, exist_ok=True)
    
    # Save QR code image
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"table_{table_number}_{timestamp}.png"
    file_path = os.path.join(qr_dir, filename)
    qr_image.save(file_path)
    
    # Return the URL path for the QR code
    return f"/static/qr_codes/{filename}"

@table_bp.route('/add', methods=['POST'])
@login_required
def add_table():
    """Add a new table."""
    data = request.get_json()
    
    if not data or 'number' not in data or 'capacity' not in data:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    # Check if table number already exists
    existing_table = Table.query.filter_by(number=data['number']).first()
    if existing_table:
        return jsonify({'success': False, 'message': 'Table number already exists'}), 400
    
    try:
        # Create new table
        table = Table(
            number=data['number'],
            capacity=data['capacity'],
            is_occupied=False
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
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    try:
        # Check if new table number conflicts with existing ones
        if 'number' in data and data['number'] != table.number:
            existing_table = Table.query.filter_by(number=data['number']).first()
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
    table = Table.query.get_or_404(id)
    
    try:
        # Delete old QR code if it exists
        if table.qr_code:
            old_qr_file = os.path.join(current_app.static_folder, table.qr_code.lstrip('/static/'))
            if os.path.exists(old_qr_file):
                os.remove(old_qr_file)
        
        # Generate new QR code
        qr_code_url = generate_qr_code(table.id, table.number)
        table.qr_code = qr_code_url
        db.session.commit()
        
        flash('QR code regenerated successfully', 'success')
        return jsonify({'success': True, 'qr_code': qr_code_url}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@table_bp.route('/list')
@login_required
def list_tables():
    """List all tables."""
    tables = Table.query.order_by(Table.number).all()
    return render_template('table/list.html', tables=tables) 