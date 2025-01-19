import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev')
    MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/dcmon')
