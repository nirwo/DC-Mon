from app.database import get_db
from app.models import Team
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Initialize the MongoDB database with required collections and indexes."""
    try:
        db = get_db()
        
        # Drop existing collections
        logger.info("Dropping existing collections...")
        db.teams.drop()
        db.applications.drop()
        db.application_instances.drop()
        
        # Create indexes
        logger.info("Creating indexes...")
        db.teams.create_index("name", unique=True)
        db.applications.create_index("name", unique=True)
        db.application_instances.create_index([("application_id", 1), ("host", 1)], unique=True)
        
        # Insert sample teams
        logger.info("Inserting sample teams...")
        sample_teams = [
            Team(name="DevOps"),
            Team(name="Development"),
            Team(name="QA"),
            Team(name="Infrastructure")
        ]
        
        for team in sample_teams:
            db.teams.insert_one(team.to_dict())
            logger.info(f"Added team: {team.name}")
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

if __name__ == "__main__":
    init_db()
