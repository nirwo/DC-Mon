from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
import threading
from config import Config

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    
    from app.routes import main as main_bp
    app.register_blueprint(main_bp)
    
    # Ensure database exists
    with app.app_context():
        if not os.path.exists(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')):
            db.create_all()
        
        # Start background worker for status checks
        if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            from app.worker import start_background_checker
            worker_thread = threading.Thread(target=start_background_checker)
            worker_thread.daemon = True
            worker_thread.start()
    
    return app
