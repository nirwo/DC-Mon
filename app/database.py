import os
from pymongo import MongoClient
from flask import current_app

def get_db():
    """Get MongoDB database instance."""
    mongo_uri = os.environ.get('MONGODB_URI', 'mongodb://mongo:27017/shutdown_manager')
    client = MongoClient(mongo_uri)
    return client.get_database()

def init_db():
    """Initialize database connection."""
    try:
        db = get_db()
        # Test MongoDB connection
        db.command('ping')
        current_app.logger.info("Successfully connected to MongoDB")
    except Exception as e:
        current_app.logger.error(f"Database initialization error: {e}")
        raise
