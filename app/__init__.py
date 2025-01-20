import os
from flask import Flask
from flask_cors import CORS
from mongoengine import connect, disconnect
from app.routes import main as main_bp

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Register blueprints
    app.register_blueprint(main_bp)
    
    with app.app_context():
        # Initialize MongoDB connection
        mongo_uri = os.environ.get('MONGODB_URI', 'mongodb://mongo:27017/shutdown_manager')
        disconnect()  # Disconnect any existing connections
        connect(host=mongo_uri)
        app.logger.info("Successfully connected to MongoDB")
            
    return app
