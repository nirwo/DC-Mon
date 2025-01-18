from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dev'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shutdown_manager.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Optimize SQLAlchemy for better performance
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 900,
        'pool_size': 50,
        'max_overflow': 100,
    }
    
    # Increase SQLite performance
    app.config['SQLALCHEMY_ENGINE_OPTIONS']['connect_args'] = {
        'timeout': 60,
        'isolation_level': None,  # Autocommit mode
        'check_same_thread': False
    }
    
    db.init_app(app)
    
    with app.app_context():
        from .routes import main
        app.register_blueprint(main)
        db.create_all()
        
    return app
