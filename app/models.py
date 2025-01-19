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
    def __init__(self, name, host=None, port=None, team_id=None, _id=None):
        self._id = _id
        self.name = name
        self.host = host
        self.port = port
        self.team_id = team_id
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    @classmethod
    def from_dict(cls, data):
        if not data:
            return None
        return cls(
            _id=data.get('_id'),
            name=data.get('name'),
            host=data.get('host'),
            port=data.get('port'),
            team_id=data.get('team_id')
        )

    def to_dict(self):
        return {
            '_id': str(self._id) if self._id else None,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'team_id': str(self.team_id) if self.team_id else None,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

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
