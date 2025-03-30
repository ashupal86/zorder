from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

# Initialize SQLAlchemy with session options
db = SQLAlchemy(engine_options={
    'pool_pre_ping': True,
    'pool_recycle': 300
})

# Initialize Flask-Migrate
migrate = Migrate()

# Initialize and configure Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
login_manager.login_message = 'Please log in to access this page.' 