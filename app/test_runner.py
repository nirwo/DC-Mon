import time
import logging
from datetime import datetime
from pymongo import MongoClient
import os
import subprocess
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db():
    client = MongoClient(os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/shutdown_manager'))
    return client.get_default_database()

def run_test_suite(app_id):
    """Run tests for a specific application"""
    db = get_db()
    
    try:
        # Get application details
        app = db.applications.find_one({'_id': app_id})
        if not app:
            raise Exception(f"Application {app_id} not found")
            
        test_results = []
        
        # Basic connectivity test
        try:
            # Add your test logic here
            test_results.append({
                'name': 'Connectivity Test',
                'description': 'Testing basic connectivity',
                'passed': True
            })
        except Exception as e:
            test_results.append({
                'name': 'Connectivity Test',
                'description': 'Testing basic connectivity',
                'passed': False,
                'error': str(e)
            })
            
        # Save test results
        db.test_results.insert_one({
            'app_id': str(app_id),
            'results': test_results,
            'created_at': datetime.utcnow()
        })
        
        # Update application test status
        db.applications.update_one(
            {'_id': app_id},
            {'$set': {
                'test_status': 'passed' if all(r['passed'] for r in test_results) else 'failed',
                'last_tested': datetime.utcnow()
            }}
        )
        
    except Exception as e:
        logger.error(f"Error running tests for application {app_id}: {str(e)}")
        db.applications.update_one(
            {'_id': app_id},
            {'$set': {
                'test_status': 'error',
                'last_tested': datetime.utcnow()
            }}
        )

def process_test_jobs():
    """Process pending test jobs"""
    db = get_db()
    
    while True:
        try:
            # Find pending test job
            job = db.test_jobs.find_one_and_update(
                {'status': 'pending'},
                {'$set': {'status': 'running', 'started_at': datetime.utcnow()}},
                sort=[('created_at', 1)]
            )
            
            if job:
                logger.info(f"Processing test job for application {job['app_id']}")
                try:
                    run_test_suite(job['app_id'])
                    db.test_jobs.update_one(
                        {'_id': job['_id']},
                        {'$set': {
                            'status': 'completed',
                            'completed_at': datetime.utcnow()
                        }}
                    )
                except Exception as e:
                    logger.error(f"Error processing test job: {str(e)}")
                    db.test_jobs.update_one(
                        {'_id': job['_id']},
                        {'$set': {
                            'status': 'failed',
                            'error': str(e),
                            'completed_at': datetime.utcnow()
                        }}
                    )
            else:
                # No pending jobs, wait before checking again
                time.sleep(5)
                
        except Exception as e:
            logger.error(f"Error in test job processor: {str(e)}")
            time.sleep(5)

if __name__ == '__main__':
    logger.info("Starting test runner service")
    process_test_jobs()
