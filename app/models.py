from datetime import datetime
from bson import ObjectId

class Team:
    def __init__(self, name, description=None, _id=None):
        self._id = ObjectId(_id) if _id else ObjectId()
        self.name = name
        self.description = description
        
    @classmethod
    def from_dict(cls, data):
        if not data:
            return None
        return cls(
            name=data["name"],
            description=data.get("description"),
            _id=data.get("_id")
        )

    def to_dict(self):
        return {
            "_id": str(self._id),
            "name": self.name,
            "description": self.description
        }

    def __repr__(self):
        return f'<Team {self.name}>'

class Application:
    def __init__(self, name, team_id=None, state="notStarted", enabled=False, _id=None):
        self._id = ObjectId(_id) if _id else ObjectId()
        self.name = name
        self.team_id = ObjectId(team_id) if team_id else None
        self.state = state
        self.enabled = enabled
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    @classmethod
    def from_dict(cls, data):
        if not data:
            return None
        app = cls(
            name=data["name"],
            team_id=data.get("team_id"),
            state=data.get("state", "notStarted"),
            enabled=data.get("enabled", False),
            _id=data.get("_id")
        )
        if 'created_at' in data:
            app.created_at = data['created_at']
        if 'updated_at' in data:
            app.updated_at = data['updated_at']
        return app

    def to_dict(self):
        return {
            "_id": str(self._id),
            "name": self.name,
            "team_id": str(self.team_id) if self.team_id else None,
            "state": self.state,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class ApplicationInstance:
    def __init__(self, application_id, host, port=None, webui_url=None, db_host=None, _id=None):
        self._id = ObjectId(_id) if _id else ObjectId()
        self.application_id = application_id  
        self.host = host
        self.port = port
        self.webui_url = webui_url
        self.db_host = db_host
        self.status = "unknown"
        self.last_check = datetime.utcnow()
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
    @classmethod
    def from_dict(cls, data):
        if not data:
            return None
        app_id = data.get('application_id')
        if isinstance(app_id, ObjectId):
            app_id = str(app_id)
        instance = cls(
            application_id=app_id,
            host=data.get('host'),
            port=data.get('port'),
            webui_url=data.get('webui_url'),
            db_host=data.get('db_host'),
            _id=data.get('_id')
        )
        if 'status' in data:
            instance.status = data['status']
        if 'last_check' in data:
            instance.last_check = data['last_check']
        if 'created_at' in data:
            instance.created_at = data['created_at']
        if 'updated_at' in data:
            instance.updated_at = data['updated_at']
        return instance

    def to_dict(self):
        return {
            '_id': str(self._id),
            'application_id': self.application_id,
            'host': self.host,
            'port': self.port,
            'webui_url': self.webui_url,
            'db_host': self.db_host,
            'status': self.status,
            'last_check': self.last_check,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

    def __repr__(self):
        return f'<ApplicationInstance {self.host}:{self.port}>'
