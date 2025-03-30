from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from models import MenuItem, db, Table, User
from utils.ai_helper import analyze_menu_text, generate_item_description, analyze_menu_image
import qrcode
import os
from PIL import Image
import pytesseract
from werkzeug.utils import secure_filename
import json
from datetime import datetime

menu_bp = Blueprint('menu', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@menu_bp.route('/menu/manage')
@login_required
def manage():
    menu_items = MenuItem.query.filter_by(user_id=current_user.id).all()
    # Convert menu items to dictionary for JSON serialization
    menu_items_json = [item.to_dict() for item in menu_items]
    return render_template('menu/manage.html', menu_items=menu_items_json)

@menu_bp.route('/menu/add', methods=['POST'])
@login_required
def add_item():
    try:
        data = request.form
        name = data.get('name')
        description = data.get('description') or generate_item_description(name)
        price = float(data.get('price'))
        category = data.get('category')
        preparation_time = int(data.get('preparation_time', 15))
        
        # Handle image upload
        image = request.files.get('image')
        image_url = None
        if image:
            filename = secure_filename(image.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            image.save(filepath)
            image_url = f'/static/uploads/{filename}'
        
        menu_item = MenuItem(
            name=name,
            description=description,
            price=price,
            category=category,
            preparation_time=preparation_time,
            image_url=image_url,
            user_id=current_user.id
        )
        
        db.session.add(menu_item)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Menu item added successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@menu_bp.route('/menu/update/<int:item_id>', methods=['PUT'])
@login_required
def update_item(item_id):
    try:
        menu_item = MenuItem.query.get_or_404(item_id)
        if menu_item.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        data = request.json
        menu_item.name = data.get('name', menu_item.name)
        menu_item.description = data.get('description', menu_item.description)
        menu_item.price = float(data.get('price', menu_item.price))
        menu_item.category = data.get('category', menu_item.category)
        menu_item.preparation_time = int(data.get('preparation_time', menu_item.preparation_time))
        menu_item.is_available = data.get('is_available', menu_item.is_available)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Menu item updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@menu_bp.route('/menu/delete/<int:item_id>', methods=['DELETE'])
@login_required
def delete_item(item_id):
    try:
        menu_item = MenuItem.query.get_or_404(item_id)
        if menu_item.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        db.session.delete(menu_item)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Menu item deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@menu_bp.route('/menu/upload', methods=['POST'])
@login_required
def upload_menu():
    try:
        if 'menu_file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['menu_file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
            
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': 'Invalid file type. Please upload a PNG or JPG image.'}), 400
        
        # Save the file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Analyze menu image with Gemini Vision
        menu_items = analyze_menu_image(filepath)
        if not menu_items:
            return jsonify({'success': False, 'message': 'Could not extract menu items from image'}), 400
        
        # Add items to database
        added_items = []
        for item in menu_items:
            menu_item = MenuItem(
                name=item['name'],
                description=item['description'],
                price=float(item['price']),
                currency=item.get('currency', 'USD'),
                category=item['category'],
                preparation_time=int(item['preparation_time']),
                image_url=item.get('image_url'),
                user_id=current_user.id
            )
            db.session.add(menu_item)
            added_items.append(menu_item.to_dict())
        
        db.session.commit()
        
        # Clean up the temporary file
        os.remove(filepath)
        
        return jsonify({
            'success': True, 
            'message': f'Menu uploaded successfully! Added {len(menu_items)} items.',
            'items': added_items
        })
    except Exception as e:
        print(f"Error in menu upload: {e}")
        return jsonify({'success': False, 'message': str(e)}), 400

@menu_bp.route('/menu/view/<int:table_id>')
def view_menu(table_id):
    try:
        # Get the table and validate it exists
        table = Table.query.get_or_404(table_id)
        
        # Get the restaurant owner's information
        restaurant = User.query.get_or_404(table.user_id)
        
        # Get all available menu items for this restaurant
        menu_items = MenuItem.query.filter_by(
            user_id=restaurant.id,
            is_available=True
        ).all()
        
        # Group menu items by category
        categories = {}
        for item in menu_items:
            category = item.category or 'Uncategorized'
            if category not in categories:
                categories[category] = {
                    'id': len(categories) + 1,
                    'name': category,
                    'menu_items': []
                }
            categories[category]['menu_items'].append(item)
        
        # Sort categories and menu items
        sorted_categories = sorted(categories.values(), key=lambda x: x['name'])
        for category in sorted_categories:
            category['menu_items'].sort(key=lambda x: x.name)
        
        return render_template('menu/view.html',
                             restaurant=restaurant,
                             table=table,
                             categories=sorted_categories)
        
    except Exception as e:
        print(f"Error viewing menu: {e}")
        abort(500)

@menu_bp.route('/menu/qr/<int:table_id>')
def generate_qr(table_id):
    menu_url = url_for('menu.view_menu', table_id=table_id, _external=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(menu_url)
    qr.make(fit=True)
    
    qr_image = qr.make_image(fill_color="black", back_color="white")
    # Save QR code image and return its URL
    qr_filename = f'qr_table_{table_id}.png'
    qr_path = os.path.join(current_app.config['UPLOAD_FOLDER'], qr_filename)
    qr_image.save(qr_path)
    
    return jsonify({'qr_url': url_for('static', filename=f'uploads/{qr_filename}')})

def process_menu_text(text):
    # Simple menu text processing logic
    # This can be enhanced with more sophisticated NLP processing
    menu_items = []
    lines = text.split('\n')
    current_category = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Assume lines with all caps are categories
        if line.isupper():
            current_category = line
        elif ' - ' in line or '\t' in line:
            # Assume format: "Item Name - $Price" or "Item Name   $Price"
            parts = line.replace('\t', ' - ').split(' - ')
            if len(parts) >= 2:
                name = parts[0].strip()
                price = parts[1].strip().replace('$', '')
                try:
                    price = float(price)
                    menu_items.append({
                        'name': name,
                        'price': price,
                        'category': current_category
                    })
                except ValueError:
                    continue
                    
    return menu_items 