from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
import threading
from config import Config
from app.models import db

migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(os.path.dirname(base_dir), 'instance', 'app.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    migrate.init_app(app, db)
    
    from app.routes import main as main_bp
    app.register_blueprint(main_bp)
    
    # Ensure database exists
    with app.app_context():
        instance_dir = os.path.dirname(db_path)
        os.makedirs(instance_dir, exist_ok=True)
        db.create_all()
        
        # Start background worker for status checks
        if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            from app.worker import start_background_checker
            worker_thread = threading.Thread(target=start_background_checker)
            worker_thread.daemon = True
            worker_thread.start()
    
    return app
