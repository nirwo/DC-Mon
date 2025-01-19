from datetime import datetime
from bson import ObjectId

class Team:
    def __init__(self, name):
        self.name = name
        
    @staticmethod
    def from_dict(data):
        team = Team(data['name'])
        team._id = data.get('_id', ObjectId())
        return team
        
    def to_dict(self):
        return {
            '_id': self._id,
            'name': self.name
        }

    def __repr__(self):
        return f'<Team {self.name}>'

class Application:
    def __init__(self, name, team_id, shutdown_order=None, dependencies=None):
        self.name = name
        self.team_id = team_id
        self.shutdown_order = shutdown_order
        self.dependencies = dependencies or []
        
    @staticmethod
    def from_dict(data):
        app = Application(
            data['name'],
            data['team_id'],
            data.get('shutdown_order'),
            data.get('dependencies', [])
        )
        app._id = data.get('_id', ObjectId())
        return app
        
    def to_dict(self):
        return {
            '_id': self._id,
            'name': self.name,
            'team_id': self.team_id,
            'shutdown_order': self.shutdown_order,
            'dependencies': self.dependencies
        }

    def __repr__(self):
        return f'<Application {self.name}>'

class ApplicationInstance:
    def __init__(self, application_id, host, port=None, webui_url=None, db_host=None):
        self.application_id = application_id
        self.host = host
        self.port = port
        self.webui_url = webui_url
        self.db_host = db_host
        self.status = 'unknown'
        self.details = None
        self.last_checked = datetime.utcnow()
        
    @staticmethod
    def from_dict(data):
        instance = ApplicationInstance(
            data['application_id'],
            data['host'],
            data.get('port'),
            data.get('webui_url'),
            data.get('db_host')
        )
        instance._id = data.get('_id', ObjectId())
        instance.status = data.get('status', 'unknown')
        instance.details = data.get('details')
        instance.last_checked = data.get('last_checked', datetime.utcnow())
        return instance
        
    def to_dict(self):
        return {
            '_id': self._id,
            'application_id': self.application_id,
            'host': self.host,
            'port': self.port,
            'webui_url': self.webui_url,
            'db_host': self.db_host,
            'status': self.status,
            'details': self.details,
            'last_checked': self.last_checked
        }

    def __repr__(self):
        return f'<ApplicationInstance {self.host}:{self.port}>'
