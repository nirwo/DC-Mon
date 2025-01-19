from pymongo import MongoClient
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_mongodb():
    try:
        # Connect to MongoDB
        mongo_uri = os.environ.get('MONGODB_URI', 'mongodb://mongo:27017/shutdown_manager')
        mongo_client = MongoClient(mongo_uri)
        mongo_db = mongo_client.get_database()

        # Drop existing collections
        mongo_db.teams.drop()
        mongo_db.applications.drop()
        mongo_db.application_instances.drop()

        # Create indexes
        mongo_db.applications.create_index('name', unique=True)
        mongo_db.teams.create_index('name', unique=True)
        
        # Insert sample data
        teams = [
            {'name': 'Team A'},
            {'name': 'Team B'},
        ]
        
        for team in teams:
            try:
                result = mongo_db.teams.insert_one(team)
                logger.info(f"Created team: {team['name']}")
            except Exception as e:
                logger.warning(f"Error creating team {team['name']}: {e}")

        logger.info("MongoDB initialization completed successfully")
        
    except Exception as e:
        logger.error(f"MongoDB initialization failed: {e}")
        raise
    finally:
        if 'mongo_client' in locals():
            mongo_client.close()

if __name__ == '__main__':
    init_mongodb()
