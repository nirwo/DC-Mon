import os
import logging
from datetime import datetime
from mongoengine import connect, disconnect
from app.models import Team, Application, System, ApplicationInstance

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Initialize the database with required collections and indexes."""
    # Setup MongoDB connection
    mongo_uri = os.environ.get('MONGODB_URI', 'mongodb://mongo:27017/shutdown_manager')
    disconnect()  # Disconnect any existing connections
    connect(host=mongo_uri)
    
    logger.info("Dropping existing collections...")
    Team.drop_collection()
    Application.drop_collection()
    System.drop_collection()
    ApplicationInstance.drop_collection()
    
    logger.info("Creating indexes...")
    
    # Insert sample teams
    logger.info("Inserting sample teams...")
    teams = [
        {"name": "DevOps"},
        {"name": "Development"},
        {"name": "QA"},
        {"name": "Infrastructure"}
    ]
    
    team_objects = {}
    for team_data in teams:
        team = Team(**team_data).save()
        team_objects[team.name] = team
        logger.info(f"Added team: {team.name}")
    
    # Insert sample applications
    logger.info("Inserting sample applications...")
    applications = [
        {
            "name": "Web Server",
            "team": team_objects["DevOps"],
            "description": "Web Server Application",
            "webui_url": "http://example.com"
        },
        {
            "name": "Database",
            "team": team_objects["DevOps"],
            "description": "Database Application",
            "webui_url": "http://example.com"
        }
    ]
    
    app_objects = {}
    for app_data in applications:
        app = Application(**app_data).save()
        app_objects[app.name] = app
        logger.info(f"Added application: {app.name}")
    
    # Insert sample systems
    logger.info("Inserting sample systems...")
    systems = [
        {
            "name": "Web Server 1",
            "application": app_objects["Web Server"],
            "host": "webserver1.example.com",
            "port": 80,
            "status": "unknown",
            "webui_url": "http://webserver1.example.com"
        },
        {
            "name": "Web Server 2",
            "application": app_objects["Web Server"],
            "host": "webserver2.example.com",
            "port": 80,
            "status": "unknown",
            "webui_url": "http://webserver2.example.com"
        },
        {
            "name": "Database Primary",
            "application": app_objects["Database"],
            "host": "db1.example.com",
            "port": 5432,
            "status": "unknown",
            "webui_url": "http://db1.example.com:5432"
        },
        {
            "name": "Database Secondary",
            "application": app_objects["Database"],
            "host": "db2.example.com",
            "port": 5432,
            "status": "unknown",
            "webui_url": "http://db2.example.com:5432"
        }
    ]
    
    for system_data in systems:
        system = System(**system_data).save()
        app = system.application
        if system not in app.systems:
            app.systems.append(system)
            app.save()
        logger.info(f"Added system: {system.name}")
    
    logger.info("Database initialization completed successfully")

if __name__ == "__main__":
    try:
        init_db()
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
