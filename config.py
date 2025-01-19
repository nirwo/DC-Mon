import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = 'dev'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'  # Use file-based database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Optimized SQLAlchemy settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'pool_size': 3,
        'max_overflow': 5,
        'connect_args': {
            'timeout': 15,
            'check_same_thread': False
        }
    }
