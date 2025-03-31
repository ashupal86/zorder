from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
from dotenv import load_dotenv
from flask_login import LoginManager

# Import extensions
from extensions import db, migrate, login_manager, socketio
from models import User, MenuItem, Order, OrderItem, Table, Feedback

# Import blueprints
from routes.auth import auth_bp
from routes.menu import menu_bp
from routes.table import table_bp
from routes.orders import orders
from routes.socket_notifications import register_notification_handlers, push_blueprint

# Load environment variables
load_dotenv()

def create_app(config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///fooder.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
    
    # Server configuration for QR codes
    if os.environ.get('SERVER_NAME'):
        app.config['SERVER_NAME'] = os.environ.get('SERVER_NAME')
    app.config['PREFERRED_URL_SCHEME'] = os.environ.get('PREFERRED_URL_SCHEME', 'http')
    
    # VAPID keys for Web Push Notifications
    app.config['VAPID_PUBLIC_KEY'] = os.environ.get('VAPID_PUBLIC_KEY', 'BDPQoiUyGUxNMKfyjHyuRu8IoS5ytMGHNhrPBFUJ6C0ylsJ64Ku5tVfKfEqD4ahT0-N7iU-f6Ss8sTZ04i78XBw')
    app.config['VAPID_PRIVATE_KEY'] = os.environ.get('VAPID_PRIVATE_KEY', 'I8QsjTuHvUhEjG3Vk7O8OD24eVjcjCz1ElMNXWqBm0A')
    app.config['VAPID_CLAIM_EMAIL'] = os.environ.get('VAPID_CLAIM_EMAIL', 'contact@digitalwaiter.com')
    
    # Apply any extra config
    if config is not None:
        if isinstance(config, dict):
            app.config.update(config)
        else:
            app.config.from_object(config)
    
    # Ensure upload directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, 'qr_codes'), exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, 'sounds'), exist_ok=True)
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(menu_bp)
    app.register_blueprint(table_bp)
    app.register_blueprint(orders)
    app.register_blueprint(push_blueprint)
    
    # Initialize Socket.IO with the app
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Register notification handlers
    with app.app_context():
        register_notification_handlers()
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.context_processor
    def inject_vapid_key():
        """Make VAPID public key available to all templates."""
        return {'vapid_public_key': app.config['VAPID_PUBLIC_KEY']}
    
    return app

# Create the application instance
app = create_app()

# Initialize database
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True) 