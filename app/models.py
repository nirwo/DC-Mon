from app import db
from datetime import datetime

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    applications = db.relationship('Application', backref='team', lazy=True)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    shutdown_order = db.Column(db.Integer, default=100)
    instances = db.relationship('ApplicationInstance', backref='application', lazy=True, cascade='all, delete-orphan')
    dependencies = db.relationship(
        'ApplicationDependency',
        foreign_keys='ApplicationDependency.application_id',
        backref=db.backref('application', lazy=True),
        lazy=True,
        cascade='all, delete-orphan'
    )

class ApplicationInstance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    host = db.Column(db.String(200), nullable=False)
    port = db.Column(db.Integer)
    webui_url = db.Column(db.String(200))
    db_host = db.Column(db.String(200))
    last_checked = db.Column(db.DateTime)
    is_running = db.Column(db.Boolean, default=True)
    status_details = db.Column(db.Text)
    
    __table_args__ = (
        db.UniqueConstraint('application_id', 'host', name='unique_app_host'),
    )

class ApplicationDependency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    dependency_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    dependency_type = db.Column(db.String(50), nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('application_id', 'dependency_id', name='unique_dependency'),
    )
