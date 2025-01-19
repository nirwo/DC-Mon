import socket
import time
from datetime import datetime
from threading import Thread
from flask import current_app
from app.database import get_db
from app.models import Application, ApplicationInstance

def check_status(host, port):
    """Check if host:port is accessible"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)  # Reduced timeout
        result = sock.connect_ex((host, int(port or 80)))
        sock.close()
        return True if result == 0 else False, None
    except (socket.gaierror, socket.timeout, ValueError):
        return False, "Connection failed"
    except Exception as e:
        return False, str(e)

def background_status_check(app):
    """Background task to check all application statuses"""
    with app.app_context():
        try:
            db = get_db()
            
            # Get all applications
            applications = list(db.applications.find())
            
            # Process in smaller batches
            batch_size = 5
            for i in range(0, len(applications), batch_size):
                batch = applications[i:i+batch_size]
                
                for app_data in batch:
                    # Get all instances for this application
                    instances = list(db.instances.find({'application_id': app_data['_id']}))
                    total_instances = len(instances)
                    down_count = 0
                    
                    for instance_data in instances:
                        is_up, error = check_status(instance_data['host'], instance_data.get('port'))
                        
                        # Update instance status
                        db.instances.update_one(
                            {'_id': instance_data['_id']},
                            {
                                '$set': {
                                    'status': 'UP' if is_up else 'DOWN',
                                    'error_message': None if is_up else error,
                                    'last_checked': datetime.utcnow()
                                }
                            }
                        )
                        
                        if not is_up:
                            down_count += 1
                    
                    # Update application status
                    app_status = 'UP' if down_count == 0 else 'PARTIAL' if down_count < total_instances else 'DOWN'
                    db.applications.update_one(
                        {'_id': app_data['_id']},
                        {'$set': {'status': app_status}}
                    )
                    
                # Sleep between batches to reduce load
                time.sleep(1)
                
        except Exception as e:
            current_app.logger.error(f"Error in background status check: {str(e)}")
        finally:
            # Sleep before next round
            time.sleep(60)

def run_checker():
    while True:
        with current_app.app_context():
            try:
                background_status_check(current_app._get_current_object())
            except Exception as e:
                current_app.logger.error(f"Background checker error: {str(e)}")
                time.sleep(60)  # Sleep on error before retrying

def start_background_checker():
    """Start the background checker thread."""
    checker_thread = Thread(target=run_checker)
    checker_thread.daemon = True
    checker_thread.start()
    return checker_thread
