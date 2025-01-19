from app import db
from datetime import datetime

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    applications = db.relationship('Application', backref='team', lazy=True)

    def __repr__(self):
        return f'<Team {self.name}>'

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    instances = db.relationship('ApplicationInstance', backref='application', lazy=True, cascade='all, delete-orphan')
    status = db.Column(db.String(50))
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Application {self.name}>'

class ApplicationInstance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    host = db.Column(db.String(120), nullable=False)
    port = db.Column(db.Integer)
    webui_url = db.Column(db.String(200))
    db_host = db.Column(db.String(120))
    status = db.Column(db.String(20))
    error_message = db.Column(db.String(200))
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('application_id', 'host', name='uix_app_host'),
    )

    def __repr__(self):
        return f'<Instance {self.host}:{self.port}>'
