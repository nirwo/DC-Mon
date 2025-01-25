from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask import current_app

db = SQLAlchemy()

# Association table for many-to-many relationship between applications and systems
application_systems = db.Table('application_systems',
    db.Column('application_id', db.Integer, db.ForeignKey('applications.id'), primary_key=True),
    db.Column('system_id', db.Integer, db.ForeignKey('systems.id'), primary_key=True)
)

class Team(db.Model):
    __tablename__ = 'teams'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    applications = db.relationship('Application', backref='team_ref', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Application(db.Model):
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    description = db.Column(db.String(500))
    webui_url = db.Column(db.String(200))
    state = db.Column(db.String(50), default='notStarted')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    systems = db.relationship('System', secondary=application_systems, lazy='joined',
        backref=db.backref('applications', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'team_id': self.team_id,
            'team_name': self.team_ref.name if self.team_ref else None,
            'description': self.description,
            'webui_url': self.webui_url,
            'state': self.state,
            'systems': [system.to_dict() for system in self.systems],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class System(db.Model):
    __tablename__ = 'systems'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    host = db.Column(db.String(200), nullable=False)
    port = db.Column(db.Integer)
    status = db.Column(db.String(20), default='unknown')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
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
    sequence = db.Column(db.Integer, default=1)  # 1 for bulk, 2+ for sequence
    
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
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'sequence': self.sequence
        }

def init_db():
    # Create tables
    db.create_all()
    
    # Add test data only if tables are empty
    if not Team.query.first():
        # Create teams
        team1 = Team(name="Development Team")
        team2 = Team(name="Operations Team")
        db.session.add(team1)
        db.session.add(team2)
        db.session.commit()

        # Create applications
        app1 = Application(
            name="Web Server",
            team_id=team1.id,
            description="Main web server",
            webui_url="http://localhost:8080",
            state="running"
        )
        app2 = Application(
            name="Database",
            team_id=team2.id,
            description="PostgreSQL Database",
            webui_url="http://localhost:5432",
            state="running"
        )
        db.session.add(app1)
        db.session.add(app2)
        db.session.commit()

        # Create systems
        system1 = System(
            name="WebServer1",
            host="webserver1.local",
            port=8080,
            status="running"
        )
        system2 = System(
            name="Database1",
            host="db1.local",
            port=5432,
            status="running"
        )
        db.session.add(system1)
        db.session.add(system2)
        db.session.commit()

        # Link systems to applications
        app1.systems.append(system1)
        app2.systems.append(system2)
        db.session.commit()
