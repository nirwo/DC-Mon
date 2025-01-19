import os
from flask import Flask
from config import Config
from app.database import get_db

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    from app.routes import main as main_bp
    app.register_blueprint(main_bp)
    
    # Initialize MongoDB connection
    with app.app_context():
        try:
            db = get_db()
            # Test MongoDB connection
            db.command('ping')
            app.logger.info("Successfully connected to MongoDB")
        except Exception as e:
            app.logger.error(f"Database initialization error: {e}")
            
        # Start background worker for status checks
        if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            from app.worker import start_background_checker
            start_background_checker()
            
    return app
