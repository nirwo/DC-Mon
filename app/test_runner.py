import os
import time
import logging
import subprocess
from datetime import datetime
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db():
    client = MongoClient(os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/shutdown_manager'))
    return client.get_default_database()

def check_system_status():
    """Run ping test on all systems"""
    db = get_db()
    logger.info("Starting system check")
    
    try:
        # Get all systems
        systems = list(db.systems.find())
        for system in systems:
            try:
                host = system.get('host')
                if not host:
                    logger.error(f"System {system['_id']} has no host")
                    continue
                    
                logger.info(f"Testing {host}")
                
                # Simple ping test
                ping_cmd = ['ping', '-c', '1', '-W', '2', host]
                result = subprocess.run(ping_cmd, capture_output=True, text=True)
                
                # Update system status
                new_status = 'running' if result.returncode == 0 else 'stopped'
                db.systems.update_one(
                    {'_id': system['_id']},
                    {'$set': {
                        'status': new_status,
                        'last_checked': datetime.utcnow()
                    }}
                )
                
                logger.info(f"System {host} status updated to: {new_status}")
                
            except Exception as e:
                logger.error(f"Error checking system {system.get('host', 'unknown')}: {str(e)}")
                # Set status to unknown on error
                db.systems.update_one(
                    {'_id': system['_id']},
                    {'$set': {
                        'status': 'unknown',
                        'last_checked': datetime.utcnow()
                    }}
                )
    
    except Exception as e:
        logger.error(f"Error in system check: {str(e)}")

def main():
    """Main loop to check systems every hour"""
    logger.info("Starting system monitor service")
    
    while True:
        try:
            check_system_status()
            logger.info("System check completed, sleeping for 1 hour")
            time.sleep(3600)  # Sleep for 1 hour
            
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            time.sleep(60)  # Wait a minute before retrying on error

if __name__ == '__main__':
    main()
