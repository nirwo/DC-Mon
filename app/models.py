from datetime import datetime
import mongoengine as db

class Team(db.Document):
    name = db.StringField(required=True, unique=True)
    created_at = db.DateTimeField(default=datetime.utcnow)
    updated_at = db.DateTimeField(default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class System(db.Document):
    name = db.StringField(required=True)
    host = db.StringField(required=True)
    port = db.IntField()
    webui_url = db.StringField()
    status = db.StringField(default='unknown')
    last_checked = db.DateTimeField()
    created_at = db.DateTimeField(default=datetime.utcnow)
    updated_at = db.DateTimeField(default=datetime.utcnow)
    application = db.ReferenceField('Application', required=True)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'webui_url': self.webui_url,
            'status': self.status,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'application': {
                'id': str(self.application.id),
                'name': self.application.name
            } if self.application else None
        }

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

class Application(db.Document):
    name = db.StringField(required=True)
    team = db.ReferenceField('Team', required=True)
    systems = db.ListField(db.ReferenceField('System', reverse_delete_rule=db.PULL))
    created_at = db.DateTimeField(default=datetime.utcnow)
    updated_at = db.DateTimeField(default=datetime.utcnow)
    description = db.StringField()
    webui_url = db.StringField()
    state = db.StringField(default='notStarted', choices=['notStarted', 'inProgress', 'completed'])
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'webui_url': self.webui_url,
            'state': self.state,
            'team': self.team.to_dict() if self.team else None,
            'systems': [system.to_dict() for system in self.systems] if self.systems else [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

class ApplicationInstance(db.Document):
    application = db.ReferenceField('Application', required=True)
    host = db.StringField(required=True)
    port = db.IntField()
    webui_url = db.StringField()
    db_host = db.StringField()
    status = db.StringField(default='unknown')
    last_check = db.DateTimeField()
    created_at = db.DateTimeField(default=datetime.utcnow)
    updated_at = db.DateTimeField(default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'application': {
                'id': str(self.application.id),
                'name': self.application.name
            } if self.application else None,
            'host': self.host,
            'port': self.port,
            'webui_url': self.webui_url,
            'db_host': self.db_host,
            'status': self.status,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

def init_db():
    """Initialize the database with required collections and indexes."""
    db = get_db()
    
    # Drop existing collections
    logger.info("Dropping existing collections...")
    db.teams.drop()
    db.applications.drop()
    db.systems.drop()
    db.application_instances.drop()
    
    # Create indexes
    logger.info("Creating indexes...")
    db.teams.create_index("name", unique=True)
    db.systems.create_index("host", unique=True)
    
    # Add sample data
    logger.info("Inserting sample teams...")
    teams = [
        {"name": "DevOps"},
        {"name": "Development"},
        {"name": "QA"},
        {"name": "Infrastructure"}
    ]
    
    for team in teams:
        try:
            db.teams.insert_one(team)
            logger.info(f"Added team: {team['name']}")
        except Exception as e:
            logger.error(f"Error adding team {team['name']}: {str(e)}")
            
    # Add sample applications
    logger.info("Inserting sample applications...")
    applications = [
        {
            "name": "Web Server",
            "team": str(db.teams.find_one({"name": "DevOps"})["_id"]),
            "description": "Web Server Application",
            "webui_url": "http://example.com",
            "state": "notStarted"
        },
        {
            "name": "Database",
            "team": str(db.teams.find_one({"name": "DevOps"})["_id"]),
            "description": "Database Application",
            "webui_url": "http://example.com",
            "state": "notStarted"
        }
    ]
    
    for app in applications:
        try:
            app_id = db.applications.insert_one(app).inserted_id
            logger.info(f"Added application: {app['name']}")
            
            # Add sample systems for each application
            systems = []
            if app["name"] == "Web Server":
                systems = [
                    {
                        "name": "Web Server 1",
                        "application": str(app_id),
                        "host": "webserver1.example.com",
                        "port": 80,
                        "status": "unknown",
                        "last_checked": datetime.utcnow()
                    },
                    {
                        "name": "Web Server 2",
                        "application": str(app_id),
                        "host": "webserver2.example.com",
                        "port": 80,
                        "status": "unknown",
                        "last_checked": datetime.utcnow()
                    }
                ]
            elif app["name"] == "Database":
                systems = [
                    {
                        "name": "Database Primary",
                        "application": str(app_id),
                        "host": "db1.example.com",
                        "port": 5432,
                        "status": "unknown",
                        "last_checked": datetime.utcnow()
                    },
                    {
                        "name": "Database Secondary",
                        "application": str(app_id),
                        "host": "db2.example.com",
                        "port": 5432,
                        "status": "unknown",
                        "last_checked": datetime.utcnow()
                    }
                ]
            
            for system in systems:
                try:
                    db.systems.insert_one(system)
                    logger.info(f"Added system: {system['name']}")
                except Exception as e:
                    logger.error(f"Error adding system {system['name']}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error adding application {app['name']}: {str(e)}")
    
    logger.info("Database initialization completed successfully")
