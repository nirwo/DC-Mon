import os
import logging
from datetime import datetime
from app import create_app, db
from app.models import Team, Application, ApplicationInstance

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Initialize the database with required collections and indexes."""
    app = create_app()
    with app.app_context():
        logger.info("Dropping existing tables...")
        db.drop_all()
        
        logger.info("Creating tables...")
        db.create_all()
        
        # Insert sample teams
        logger.info("Inserting sample teams...")
        teams = [
            Team(name="DevOps"),
            Team(name="Development"),
            Team(name="QA"),
        ]
        db.session.add_all(teams)
        db.session.commit()
        
        # Insert sample applications
        logger.info("Inserting sample applications...")
        devops_team = Team.query.filter_by(name="DevOps").first()
        dev_team = Team.query.filter_by(name="Development").first()
        qa_team = Team.query.filter_by(name="QA").first()
        
        applications = [
            Application(name="Monitoring System", team_id=devops_team.id),
            Application(name="CI/CD Pipeline", team_id=devops_team.id),
            Application(name="Frontend App", team_id=dev_team.id),
            Application(name="Backend API", team_id=dev_team.id),
            Application(name="Test Framework", team_id=qa_team.id),
        ]
        db.session.add_all(applications)
        db.session.commit()
        
        # Insert sample application instances
        logger.info("Inserting sample application instances...")
        monitoring = Application.query.filter_by(name="Monitoring System").first()
        cicd = Application.query.filter_by(name="CI/CD Pipeline").first()
        frontend = Application.query.filter_by(name="Frontend App").first()
        backend = Application.query.filter_by(name="Backend API").first()
        test_framework = Application.query.filter_by(name="Test Framework").first()
        
        instances = [
            ApplicationInstance(
                application_id=monitoring.id,
                host="monitor1.example.com",
                port=8080,
                webui_url="http://monitor1.example.com:8080",
                db_host="db1.example.com",
                status="running"
            ),
            ApplicationInstance(
                application_id=cicd.id,
                host="jenkins.example.com",
                port=8080,
                webui_url="http://jenkins.example.com:8080",
                status="running"
            ),
            ApplicationInstance(
                application_id=frontend.id,
                host="web1.example.com",
                port=3000,
                webui_url="http://web1.example.com:3000",
                status="running"
            ),
            ApplicationInstance(
                application_id=backend.id,
                host="api1.example.com",
                port=5000,
                webui_url="http://api1.example.com:5000",
                db_host="db2.example.com",
                status="running"
            ),
            ApplicationInstance(
                application_id=test_framework.id,
                host="test1.example.com",
                port=4444,
                webui_url="http://test1.example.com:4444",
                status="running"
            ),
        ]
        db.session.add_all(instances)
        db.session.commit()
        
        logger.info("Database initialization completed successfully!")

if __name__ == "__main__":
    try:
        init_db()
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise
