import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = 'dev'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'  # Use file-based database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Basic SQLAlchemy settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {
            'timeout': 60,
            'check_same_thread': False
        }
    }
