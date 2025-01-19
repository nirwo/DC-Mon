import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://dcmon:dcmon@localhost:5432/dcmon')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Optimized SQLAlchemy settings for concurrent access
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'pool_size': 10,
        'max_overflow': 20,
        'pool_timeout': 30,
    }
