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

def run_test_suite(app_id):
    """Run tests for a specific application"""
    db = get_db()
    
    try:
        # Get application details
        app = db.applications.find_one({'_id': ObjectId(app_id)})
        if not app:
            raise Exception(f"Application {app_id} not found")
            
        logger.info(f"Running tests for application: {app['name']}")
        test_results = []
        
        # Get all systems for this application
        systems = list(db.systems.find({'application_id': str(app['_id'])}))
        if not systems:
            logger.warning(f"No systems found for application {app['name']}")
            test_results.append({
                'name': 'System Check',
                'description': 'Checking if application has systems',
                'passed': False,
                'error': 'No systems found for this application'
            })
        else:
            test_results.append({
                'name': 'System Check',
                'description': 'Checking if application has systems',
                'passed': True,
                'message': f"Found {len(systems)} systems"
            })
            
            # Test each system
            for system in systems:
                try:
                    # Basic connectivity test (ping)
                    host = system['host']
                    logger.info(f"Testing connectivity to {host}")
                    
                    ping_cmd = ['ping', '-c', '1', '-W', '2', host]
                    result = subprocess.run(ping_cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        test_results.append({
                            'name': f"Connectivity Test - {host}",
                            'description': 'Testing basic connectivity',
                            'passed': True,
                            'message': 'Host is reachable'
                        })
                        
                        # If port is specified, test port connectivity
                        if system.get('port'):
                            port = system['port']
                            logger.info(f"Testing port {port} on {host}")
                            
                            try:
                                import socket
                                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                sock.settimeout(2)
                                result = sock.connect_ex((host, port))
                                sock.close()
                                
                                if result == 0:
                                    test_results.append({
                                        'name': f"Port Test - {host}:{port}",
                                        'description': f"Testing port {port} connectivity",
                                        'passed': True,
                                        'message': f"Port {port} is open"
                                    })
                                else:
                                    test_results.append({
                                        'name': f"Port Test - {host}:{port}",
                                        'description': f"Testing port {port} connectivity",
                                        'passed': False,
                                        'error': f"Port {port} is closed"
                                    })
                            except Exception as e:
                                test_results.append({
                                    'name': f"Port Test - {host}:{port}",
                                    'description': f"Testing port {port} connectivity",
                                    'passed': False,
                                    'error': f"Port test failed: {str(e)}"
                                })
                    else:
                        test_results.append({
                            'name': f"Connectivity Test - {host}",
                            'description': 'Testing basic connectivity',
                            'passed': False,
                            'error': 'Host is not reachable'
                        })
                        
                except Exception as e:
                    test_results.append({
                        'name': f"System Test - {system['host']}",
                        'description': 'Testing system connectivity',
                        'passed': False,
                        'error': str(e)
                    })
        
        # Save test results
        db.test_results.insert_one({
            'app_id': str(app['_id']),
            'results': test_results,
            'created_at': datetime.utcnow()
        })
        
        # Update application test status
        all_passed = all(r['passed'] for r in test_results)
        db.applications.update_one(
            {'_id': ObjectId(app_id)},
            {'$set': {
                'test_status': 'passed' if all_passed else 'failed',
                'last_tested': datetime.utcnow()
            }}
        )
        
        logger.info(f"Tests completed for application {app['name']} - Status: {'passed' if all_passed else 'failed'}")
        
    except Exception as e:
        logger.error(f"Error running tests for application {app_id}: {str(e)}")
        db.applications.update_one(
            {'_id': ObjectId(app_id)},
            {'$set': {
                'test_status': 'error',
                'last_tested': datetime.utcnow()
            }}
        )

def process_test_jobs():
    """Process pending test jobs and run hourly system checks"""
    db = get_db()
    last_hourly_check = None
    
    while True:
        try:
            current_time = datetime.utcnow()
            
            # Run hourly system check
            if not last_hourly_check or (current_time - last_hourly_check).total_seconds() >= 3600:
                logger.info("Running hourly system check")
                
                # Get all applications
                applications = db.applications.find()
                for app in applications:
                    # Create test job for each application
                    test_job = {
                        'app_id': str(app['_id']),
                        'status': 'pending',
                        'created_at': current_time
                    }
                    db.test_jobs.insert_one(test_job)
                    logger.info(f"Created hourly test job for application {app['name']}")
                
                last_hourly_check = current_time
            
            # Process pending test jobs
            job = db.test_jobs.find_one_and_update(
                {'status': 'pending'},
                {'$set': {'status': 'running', 'started_at': current_time}},
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
            
            time.sleep(1)  # Prevent CPU overload
            
        except Exception as e:
            logger.error(f"Error in test job processor: {str(e)}")
            time.sleep(5)  # Wait before retrying

if __name__ == '__main__':
    logger.info("Starting test runner service")
    process_test_jobs()
