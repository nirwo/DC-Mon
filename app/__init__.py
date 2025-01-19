import os
from flask import Flask
from flask_cors import CORS
from config import Config
from app.database import init_db
from app.routes import main as main_bp
from app.worker import start_background_checker

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    CORS(app)
    
    # Initialize MongoDB connection
    init_db()
    
    # Register blueprints
    app.register_blueprint(main_bp)
    
    # Start background checker
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        start_background_checker(app)
            
    return app
