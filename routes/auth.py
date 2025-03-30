from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import User
from extensions import db
import logging
import traceback
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            phone = request.form.get('phone')
            address = request.form.get('address')

            # Log registration attempt
            logger.info(f"Registration attempt for email: {email}")

            # Validate required fields
            if not all([name, email, password]):
                logger.warning(f"Registration failed: Missing required fields - Name: {bool(name)}, Email: {bool(email)}, Password: {bool(password)}")
                flash('Please fill in all required fields', 'error')
                return redirect(url_for('auth.register'))

            # Check if user already exists
            if User.query.filter_by(email=email).first():
                logger.warning(f"Registration failed: Email already exists - {email}")
                flash('Email already registered', 'error')
                return redirect(url_for('auth.register'))

            # Create new user
            user = User(
                name=name,
                email=email,
                phone=phone,
                address=address
            )
            user.set_password(password)

            # Save to database
            db.session.add(user)
            db.session.commit()

            logger.info(f"Registration successful for user: {email}")
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            exc_info = sys.exc_info()
            logger.error(
                "Registration error\n"
                f"Error: {str(e)}\n"
                f"Type: {exc_info[0].__name__}\n"
                f"Traceback:\n{''.join(traceback.format_tb(exc_info[2]))}"
            )
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            return redirect(url_for('auth.register'))

    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Redirect if user is already logged in
    if current_user.is_authenticated:
        logger.info(f"Already authenticated user attempting to access login: {current_user.email}")
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            remember = request.form.get('remember', False)

            # Log login attempt
            logger.info(f"Login attempt for email: {email}")

            # Validate required fields
            if not all([email, password]):
                logger.warning(f"Login failed: Missing required fields - Email: {bool(email)}, Password: {bool(password)}")
                flash('Please fill in all fields', 'error')
                return redirect(url_for('auth.login'))

            # Check user credentials
            user = User.query.filter_by(email=email).first()
            
            if not user:
                logger.warning(f"Login failed: User not found - {email}")
                flash('Invalid email or password', 'error')
                return redirect(url_for('auth.login'))
                
            if not user.check_password(password):
                logger.warning(f"Login failed: Invalid password for user - {email}")
                flash('Invalid email or password', 'error')
                return redirect(url_for('auth.login'))
                
            # Log in user
            login_user(user, remember=bool(remember))
            logger.info(f"Login successful for user: {email}")
            
            # Redirect to next page or index
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
            
        except Exception as e:
            exc_info = sys.exc_info()
            logger.error(
                "Login error\n"
                f"Error: {str(e)}\n"
                f"Type: {exc_info[0].__name__}\n"
                f"Traceback:\n{''.join(traceback.format_tb(exc_info[2]))}"
            )
            flash('An error occurred during login. Please try again.', 'error')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    try:
        email = current_user.email  # Store email before logout for logging
        logout_user()
        logger.info(f"Logout successful for user: {email}")
        flash('You have been logged out successfully.', 'success')
    except Exception as e:
        exc_info = sys.exc_info()
        logger.error(
            "Logout error\n"
            f"Error: {str(e)}\n"
            f"Type: {exc_info[0].__name__}\n"
            f"Traceback:\n{''.join(traceback.format_tb(exc_info[2]))}"
        )
        flash('An error occurred during logout.', 'error')
    return redirect(url_for('auth.login')) 