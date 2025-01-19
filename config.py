import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = 'dev'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Optimized SQLAlchemy settings for concurrent access
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'pool_size': 1,  # Single connection for SQLite
        'max_overflow': 0,  # No overflow for SQLite
        'connect_args': {
            'timeout': 30,  # Increased timeout
            'check_same_thread': False,
            'isolation_level': 'IMMEDIATE'  # Better concurrent writes
        }
    }
