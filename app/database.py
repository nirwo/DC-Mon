import os
import time
from pymongo import MongoClient
from flask import current_app

def get_db():
    """Get MongoDB database instance."""
    mongo_uri = os.environ.get('MONGODB_URI', 'mongodb://mongo:27017/shutdown_manager')
    client = MongoClient(mongo_uri)
    return client.get_database()

def init_db(max_retries=5, retry_delay=5):
    """Initialize database connection with retries."""
    retry_count = 0
    while retry_count < max_retries:
        try:
            db = get_db()
            # Test MongoDB connection
            db.command('ping')
            current_app.logger.info("Successfully connected to MongoDB")
            
            # Create indexes
            db.applications.create_index('name', unique=True)
            db.teams.create_index('name', unique=True)
            return True
        except Exception as e:
            retry_count += 1
            if retry_count == max_retries:
                current_app.logger.error(f"Failed to connect to MongoDB after {max_retries} attempts: {e}")
                raise
            current_app.logger.warning(f"Failed to connect to MongoDB (attempt {retry_count}/{max_retries}). Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
