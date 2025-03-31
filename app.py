from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
from dotenv import load_dotenv
from flask_login import LoginManager, login_required
import logging

# Import extensions
from extensions import db, migrate, login_manager, socketio
from models import User, MenuItem, Order, OrderItem, Table, Feedback

# Import blueprints
from routes.auth import auth_bp
from routes.menu import menu_bp
from routes.table import table_bp
from routes.orders import orders
from routes.profile import profile_bp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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
    socketio.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(menu_bp)
    app.register_blueprint(table_bp)
    app.register_blueprint(orders)
    app.register_blueprint(profile_bp)
    
    # Import the socket notifications blueprint after initializing socketio
    from routes.socket_notifications import notification_bp
    app.register_blueprint(notification_bp)
    
    # Add direct routes for table management at root level
    @app.route('/tables', methods=['POST'])
    def root_add_table():
        from routes.table import add_table
        return add_table()
    
    # Add direct route for automatically adding tables
    @app.route('/auto-add-table', methods=['POST'])
    def root_auto_add_table():
        from routes.table import auto_add_table
        return auto_add_table()
    
    # Add direct route for order status updates
    @app.route('/order/<int:order_id>/status', methods=['PUT'])
    def root_update_order_status(order_id):
        from routes.orders import update_order_status
        return update_order_status(order_id)
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    return app

# Create the application instance
app = create_app()

# Initialize database
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Run with socketio instead of app.run
    socketio.run(app, host='0.0.0.0', port=5001, debug=True, allow_unsafe_werkzeug=True) 