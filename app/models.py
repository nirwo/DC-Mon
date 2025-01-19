from app import db
from datetime import datetime

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    applications = db.relationship('Application', backref='team', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Team {self.name}>'

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    shutdown_order = db.Column(db.Integer)
    instances = db.relationship('ApplicationInstance', backref='application', lazy=True, cascade='all, delete-orphan')
    dependencies = db.relationship(
        'Application',
        secondary='dependencies',
        primaryjoin='Application.id==dependencies.c.application_id',
        secondaryjoin='Application.id==dependencies.c.dependency_id',
        backref=db.backref('dependent_apps', lazy=True)
    )

    def __repr__(self):
        return f'<Application {self.name}>'

class ApplicationInstance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    host = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer)
    webui_url = db.Column(db.String(200))
    db_host = db.Column(db.String(100))
    status = db.Column(db.String(20), default='unknown')
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    error_message = db.Column(db.Text)

    def __repr__(self):
        return f'<Instance {self.host}:{self.port}>'

# Association table for application dependencies
dependencies = db.Table('dependencies',
    db.Column('application_id', db.Integer, db.ForeignKey('application.id'), primary_key=True),
    db.Column('dependency_id', db.Integer, db.ForeignKey('application.id'), primary_key=True)
)
