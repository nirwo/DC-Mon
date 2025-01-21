from datetime import datetime
from app import db

class Team(db.Model):
    __tablename__ = 'teams'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    applications = db.relationship('Application', backref='team', lazy=True, cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'application_count': len(self.applications)
        }

class System(db.Model):
    __tablename__ = 'systems'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    host = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer)
    webui_url = db.Column(db.String(200))
    status = db.Column(db.String(20), default='unknown')
    last_checked = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'webui_url': self.webui_url,
            'status': self.status,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None
        }

# Association table for many-to-many relationship between Application and System
application_systems = db.Table('application_systems',
    db.Column('application_id', db.Integer, db.ForeignKey('applications.id'), primary_key=True),
    db.Column('system_id', db.Integer, db.ForeignKey('systems.id'), primary_key=True)
)

class Application(db.Model):
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    description = db.Column(db.Text)
    webui_url = db.Column(db.String(200))
    state = db.Column(db.String(20), default='notStarted')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    systems = db.relationship('System', secondary=application_systems, lazy='subquery',
                            backref=db.backref('applications', lazy=True))
    instances = db.relationship('ApplicationInstance', backref='application', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'team_id': self.team_id,
            'description': self.description,
            'webui_url': self.webui_url,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'systems': [system.to_dict() for system in self.systems]
        }

class ApplicationInstance(db.Model):
    __tablename__ = 'application_instances'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    host = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer)
    webui_url = db.Column(db.String(200))
    db_host = db.Column(db.String(100))
    status = db.Column(db.String(20), default='unknown')
    last_check = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'host': self.host,
            'port': self.port,
            'webui_url': self.webui_url,
            'db_host': self.db_host,
            'status': self.status,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

def init_db():
    """Initialize the database with required tables and indexes."""
    db.create_all()
    
    # Add sample data
    teams = [
        {"name": "DevOps"},
        {"name": "Development"},
        {"name": "QA"},
        {"name": "Infrastructure"}
    ]
    
    for team in teams:
        db.session.add(Team(**team))
    
    db.session.commit()
    
    # Add sample applications
    applications = [
        {
            "name": "Web Server",
            "team_id": 1,
            "description": "Web Server Application",
            "webui_url": "http://example.com",
            "state": "notStarted"
        },
        {
            "name": "Database",
            "team_id": 1,
            "description": "Database Application",
            "webui_url": "http://example.com",
            "state": "notStarted"
        }
    ]
    
    for app in applications:
        db.session.add(Application(**app))
    
    db.session.commit()
    
    # Add sample systems for each application
    systems = []
    for app in applications:
        if app["name"] == "Web Server":
            systems = [
                {
                    "name": "Web Server 1",
                    "host": "webserver1.example.com",
                    "port": 80,
                    "status": "unknown",
                    "last_checked": datetime.utcnow()
                },
                {
                    "name": "Web Server 2",
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
                    "host": "db1.example.com",
                    "port": 5432,
                    "status": "unknown",
                    "last_checked": datetime.utcnow()
                },
                {
                    "name": "Database Secondary",
                    "host": "db2.example.com",
                    "port": 5432,
                    "status": "unknown",
                    "last_checked": datetime.utcnow()
                }
            ]
        
        for system in systems:
            db.session.add(System(**system))
    
    db.session.commit()
    
    # Add sample application-system associations
    for app in applications:
        if app["name"] == "Web Server":
            app_id = Application.query.filter_by(name="Web Server").first().id
            system_ids = [system.id for system in System.query.filter(System.name.in_(["Web Server 1", "Web Server 2"])).all()]
            for system_id in system_ids:
                db.session.execute(application_systems.insert().values(application_id=app_id, system_id=system_id))
        elif app["name"] == "Database":
            app_id = Application.query.filter_by(name="Database").first().id
            system_ids = [system.id for system in System.query.filter(System.name.in_(["Database Primary", "Database Secondary"])).all()]
            for system_id in system_ids:
                db.session.execute(application_systems.insert().values(application_id=app_id, system_id=system_id))
    
    db.session.commit()
