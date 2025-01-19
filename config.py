import os

class Config:
    SECRET_KEY = 'dev'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///shutdown_manager.db'
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
