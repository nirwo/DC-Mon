import os
from flask import Flask
from flask_cors import CORS
from app.database import init_db
from app.routes import main as main_bp
from app.worker import start_background_checker

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Register blueprints
    app.register_blueprint(main_bp)
    
    with app.app_context():
        # Initialize MongoDB connection
        init_db()
        
        # Start background checker
        if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            start_background_checker(app)
            
    return app
