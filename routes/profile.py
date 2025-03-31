from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import logging
from models import User, db
from werkzeug.security import check_password_hash, generate_password_hash

# Create profile blueprint
profile_bp = Blueprint('profile', __name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file, path, user_id):
    """Save uploaded file with a secure filename."""
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{user_id}_{file.filename}")
        file_path = os.path.join(path, filename)
        file.save(file_path)
        # Return URL path for static files
        return f"/static/uploads/{filename}"
    return None

@profile_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    """Display the profile page."""
    return render_template('profile.html')

@profile_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Update the user's profile information."""
    try:
        # Get form data
        restaurant_name = request.form.get('restaurant_name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        country = request.form.get('country')
        currency = request.form.get('currency')
        tax_rate = request.form.get('tax_rate')
        
        # Get file uploads
        logo = request.files.get('logo')
        qr_code = request.files.get('qr_code')
        
        # Update user data
        user = User.query.get(current_user.id)
        if user:
            user.restaurant_name = restaurant_name
            user.phone = phone
            user.address = address
            user.country = country
            user.currency = currency
            
            # Convert tax_rate to float if provided
            if tax_rate:
                try:
                    user.tax_rate = float(tax_rate)
                except ValueError:
                    flash('Invalid tax rate value', 'warning')
            
            # Handle logo upload
            if logo and logo.filename:
                upload_folder = current_app.config['UPLOAD_FOLDER']
                logo_url = save_file(logo, upload_folder, user.id)
                if logo_url:
                    user.logo_url = logo_url
            
            # Handle QR code upload
            if qr_code and qr_code.filename:
                upload_folder = current_app.config['UPLOAD_FOLDER']
                qr_url = save_file(qr_code, upload_folder, user.id)
                if qr_url:
                    user.qr_code = qr_url
            
            # Save changes
            db.session.commit()
            flash('Profile updated successfully!', 'success')
        else:
            flash('User not found', 'error')
        
        return redirect(url_for('profile.profile'))
    
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        db.session.rollback()
        flash('An error occurred while updating your profile', 'error')
        return redirect(url_for('profile.profile'))

@profile_bp.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    """Change the user's password."""
    try:
        # Get form data
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate password match
        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return redirect(url_for('profile.profile'))
        
        # Update password
        user = User.query.get(current_user.id)
        if user and user.check_password(current_password):
            user.set_password(new_password)
            db.session.commit()
            flash('Password changed successfully!', 'success')
        else:
            flash('Current password is incorrect', 'error')
        
        return redirect(url_for('profile.profile'))
    
    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        db.session.rollback()
        flash('An error occurred while changing your password', 'error')
        return redirect(url_for('profile.profile')) 