from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    applications = db.relationship('Application', backref='team', lazy=True)

    def __repr__(self):
        return f'<Team {self.name}>'

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    shutdown_order = db.Column(db.Integer)
    instances = db.relationship('ApplicationInstance', backref='application', lazy=True)
    dependencies = db.Column(db.JSON)

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
    details = db.Column(db.Text)
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ApplicationInstance {self.host}:{self.port}>'
