from . import db
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import String

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    applications = db.relationship('Application', backref='team', lazy=True)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    shutdown_order = db.Column(db.Integer, default=100)
    _dependencies = db.Column('dependencies', db.Text, default='')
    instances = db.relationship('ApplicationInstance', backref='application', lazy=True, cascade='all, delete-orphan')
    
    @property
    def dependencies(self):
        return self._dependencies.split(';') if self._dependencies else []
    
    @dependencies.setter
    def dependencies(self, value):
        if isinstance(value, list):
            self._dependencies = ';'.join(value)
        else:
            self._dependencies = value

class ApplicationInstance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    host = db.Column(db.String(200), nullable=False)
    port = db.Column(db.Integer)
    webui_url = db.Column(db.String(500))
    db_host = db.Column(db.String(200))
    status = db.Column(db.String(50), default='unknown')
    last_checked = db.Column(db.DateTime)
    
    __table_args__ = (
        db.UniqueConstraint('application_id', 'host', name='uix_app_host'),
    )
