from app import db
from datetime import datetime

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    applications = db.relationship('Application', backref='team', lazy=True)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer)
    webui_url = db.Column(db.String(255))
    db_host = db.Column(db.String(255))
    shutdown_order = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='running')
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    dependencies = db.relationship('ApplicationDependency', 
                                 foreign_keys='ApplicationDependency.application_id',
                                 backref='application', lazy=True)

class ApplicationDependency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    dependency_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    dependency_type = db.Column(db.String(50), nullable=False)  # e.g., 'shutdown_before', 'shutdown_after'
