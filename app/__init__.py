from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dev'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shutdown_manager.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Basic SQLAlchemy settings
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # SQLite optimizations
    app.config['SQLALCHEMY_ENGINE_OPTIONS']['connect_args'] = {
        'timeout': 60,
        'check_same_thread': False
    }
    
    db.init_app(app)
    migrate.init_app(app, db)
    
    with app.app_context():
        db.create_all()  # Create database tables
        
        from .routes import main
        app.register_blueprint(main)
        
    return app
