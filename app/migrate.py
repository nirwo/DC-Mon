import logging
from datetime import datetime
from database import get_db
from models import Team, Application

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Initialize the database with sample data"""
    try:
        db = get_db()
        
        # Drop existing collections
        logger.info("Dropping existing collections...")
        db.teams.drop()
        db.applications.drop()
        
        # Create indexes
        logger.info("Creating indexes...")
        db.teams.create_index("name", unique=True)
        db.applications.create_index("name", unique=True)
        
        # Insert sample teams
        logger.info("Inserting sample teams...")
        teams = [
            {"name": "DevOps", "description": "DevOps Team"},
            {"name": "Development", "description": "Development Team"},
            {"name": "QA", "description": "Quality Assurance Team"},
            {"name": "Infrastructure", "description": "Infrastructure Team"}
        ]
        
        team_ids = {}
        for team_data in teams:
            team = Team(**team_data)
            result = db.teams.insert_one(team.to_dict())
            team_ids[team.name] = str(result.inserted_id)
            logger.info(f"Added team: {team.name}")
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

if __name__ == "__main__":
    init_db()
