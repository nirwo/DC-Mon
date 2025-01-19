import socket
import time
from datetime import datetime
from threading import Thread
from flask import current_app
from app import db, create_app
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
            # Process in smaller batches
            batch_size = 10
            applications = Application.query.all()
            
            for i in range(0, len(applications), batch_size):
                batch = applications[i:i+batch_size]
                for app_instance in batch:
                    down_count = 0
                    total_instances = len(app_instance.instances)
                    
                    for instance in app_instance.instances:
                        is_up, error = check_status(instance.host, instance.port)
                        instance.status = 'UP' if is_up else 'DOWN'
                        instance.error_message = None if is_up else error
                        if not is_up:
                            down_count += 1
                        instance.last_checked = datetime.utcnow()
                    
                    app_instance.status = 'UP' if down_count == 0 else f'DOWN ({down_count}/{total_instances})'
                    app_instance.last_checked = datetime.utcnow()
                
                db.session.commit()
                time.sleep(0.1)  # Small delay between batches
                
        except Exception as e:
            current_app.logger.error(f"Background status check error: {str(e)}")
            db.session.rollback()
        finally:
            db.session.remove()

def start_background_checker():
    """Start the background status checker thread"""
    app = create_app()
    
    def run_checker():
        with app.app_context():
            while True:
                try:
                    background_status_check(app)
                except Exception as e:
                    current_app.logger.error(f"Checker thread error: {str(e)}")
                time.sleep(3600)  # Check every hour
    
    checker_thread = Thread(target=run_checker, daemon=True)
    checker_thread.start()
    return checker_thread
