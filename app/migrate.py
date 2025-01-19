import logging
from datetime import datetime
from database import get_db
from models import Team, Application, System
from bson import ObjectId

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
        db.systems.drop()
        
        # Create indexes
        logger.info("Creating indexes...")
        db.teams.create_index("name", unique=True)
        db.applications.create_index("name", unique=True)
        db.systems.create_index([("application_id", 1), ("name", 1)], unique=True)
        
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
            
        # Insert sample applications
        logger.info("Inserting sample applications...")
        applications = [
            {
                "name": "Web Server",
                "team_id": ObjectId(team_ids["Infrastructure"]),
                "state": "notStarted",
                "enabled": False,
                "systems": []
            },
            {
                "name": "Database",
                "team_id": ObjectId(team_ids["DevOps"]),
                "state": "notStarted",
                "enabled": False,
                "systems": []
            }
        ]
        
        app_ids = {}
        for app_data in applications:
            app = Application(**app_data)
            result = db.applications.insert_one(app.to_dict())
            app_ids[app.name] = str(result.inserted_id)
            logger.info(f"Added application: {app.name}")
            
        # Insert sample systems
        logger.info("Inserting sample systems...")
        systems = [
            {
                "name": "Web Server 1",
                "application_id": str(app_ids["Web Server"]),
                "status": "stopped",
                "last_checked": datetime.utcnow()
            },
            {
                "name": "Web Server 2",
                "application_id": str(app_ids["Web Server"]),
                "status": "stopped",
                "last_checked": datetime.utcnow()
            },
            {
                "name": "Database Primary",
                "application_id": str(app_ids["Database"]),
                "status": "stopped",
                "last_checked": datetime.utcnow()
            },
            {
                "name": "Database Secondary",
                "application_id": str(app_ids["Database"]),
                "status": "stopped",
                "last_checked": datetime.utcnow()
            }
        ]
        
        for system_data in systems:
            system = System(**system_data)
            result = db.systems.insert_one(system.to_dict())
            
            # Add system to application's systems list
            db.applications.update_one(
                {"_id": ObjectId(system.application_id)},
                {"$push": {"systems": str(result.inserted_id)}}
            )
            
            logger.info(f"Added system: {system.name}")
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

if __name__ == "__main__":
    init_db()
