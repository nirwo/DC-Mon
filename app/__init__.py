import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config, ProductionConfig, DevelopmentConfig

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_name='development'):
    app = Flask(__name__)
    
    # Configure the app
    if config_name == 'production':
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Configure logging for production
    if not app.debug and not app.testing:
        if app.config['LOG_TO_STDOUT']:
            import logging
            from logging import StreamHandler
            stream_handler = StreamHandler()
            stream_handler.setLevel(logging.INFO)
            app.logger.addHandler(stream_handler)
            app.logger.setLevel(logging.INFO)
            app.logger.info('Shutdown Manager startup')
    
    # Register blueprints
    from .routes import main
    app.register_blueprint(main)
    
    return app

from app import models
