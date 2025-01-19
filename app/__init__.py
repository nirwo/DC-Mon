from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
import threading

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
        
    # Start background worker for status checks
    def start_background_worker():
        from app.worker import start_background_checker
        with app.app_context():
            start_background_checker()
    
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        worker_thread = threading.Thread(target=start_background_worker)
        worker_thread.daemon = True
        worker_thread.start()
        
    from .routes import main
    app.register_blueprint(main)
    
    return app
