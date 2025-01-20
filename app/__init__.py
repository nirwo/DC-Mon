import os
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from mongoengine import connect, disconnect

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Configure SQLAlchemy
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    
    # Import and register blueprints
    from app.routes import main as main_bp
    app.register_blueprint(main_bp)
    
    with app.app_context():
        # Create SQLite tables
        db.create_all()
        
        # Initialize MongoDB connection
        mongo_uri = os.environ.get('MONGODB_URI', 'mongodb://mongo:27017/shutdown_manager')
        disconnect()  # Disconnect any existing connections
        connect(host=mongo_uri)
        app.logger.info("Successfully connected to MongoDB")
            
    return app
