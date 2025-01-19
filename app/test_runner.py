import time
import logging
from datetime import datetime
from pymongo import MongoClient, ObjectId
import os
import subprocess
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db():
    client = MongoClient(os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/shutdown_manager'))
    return client.get_default_database()

def check_system_status():
    """Run hourly ping test on all systems"""
    db = get_db()
    logger.info("Starting hourly system check")
    
    try:
        # Get all systems
        systems = list(db.systems.find())
        for system in systems:
            try:
                host = system['host']
                logger.info(f"Testing {host}")
                
                # Simple ping test
                ping_cmd = ['ping', '-c', '1', '-W', '2', host]
                result = subprocess.run(ping_cmd, capture_output=True, text=True)
                
                status = 'running' if result.returncode == 0 else 'stopped'
                
                # Update system status
                db.systems.update_one(
                    {'_id': system['_id']},
                    {'$set': {
                        'status': status,
                        'last_checked': datetime.utcnow()
                    }}
                )
                
                logger.info(f"System {host} status: {status}")
                
            except Exception as e:
                logger.error(f"Error checking system {system['host']}: {str(e)}")
                db.systems.update_one(
                    {'_id': system['_id']},
                    {'$set': {
                        'status': 'unknown',
                        'last_checked': datetime.utcnow()
                    }}
                )
    
    except Exception as e:
        logger.error(f"Error in system check: {str(e)}")

def run_hourly_checks():
    """Run system checks every hour"""
    last_check = None
    
    while True:
        try:
            current_time = datetime.utcnow()
            
            # Run check if it's the first run or an hour has passed
            if not last_check or (current_time - last_check).total_seconds() >= 3600:
                check_system_status()
                last_check = current_time
            
            time.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Error in hourly check: {str(e)}")
            time.sleep(60)  # Wait before retrying

if __name__ == '__main__':
    logger.info("Starting system monitor service")
    run_hourly_checks()
