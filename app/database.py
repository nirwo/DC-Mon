from pymongo import MongoClient
import os

def get_db():
    client = MongoClient(os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/dcmon'))
    return client.dcmon
