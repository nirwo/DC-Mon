from . import db
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import String
from datetime import datetime

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    applications = db.relationship('Application', backref='team', lazy=True)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    state = db.Column(db.String(20), default='unknown')  # up, down, partial, unknown
    shutdown_order = db.Column(db.Integer, default=100)
    _dependencies = db.Column('dependencies', db.Text, default='')
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    
    instances = db.relationship('ApplicationInstance', backref='application', lazy=True, cascade='all, delete-orphan')
    
    @property
    def dependencies(self):
        if not self._dependencies:
            return []
        return [int(x) for x in self._dependencies.split(',') if x]
    
    @dependencies.setter
    def dependencies(self, value):
        if isinstance(value, list):
            self._dependencies = ','.join(str(x) for x in value)
        else:
            self._dependencies = str(value)

class ApplicationInstance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    host = db.Column(db.String(120), nullable=False)
    port = db.Column(db.Integer)
    webui_url = db.Column(db.String(200))
    db_host = db.Column(db.String(120))
    status = db.Column(db.String(20), default='unknown')  # unknown, running, stopped, in_progress
    error_message = db.Column(db.String(200))
    last_checked = db.Column(db.DateTime)
    
    __table_args__ = (
        db.UniqueConstraint('application_id', 'host', name='uix_app_host'),
    )
    
    def __repr__(self):
        return f'<Instance {self.host}:{self.port}>'
