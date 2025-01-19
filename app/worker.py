import socket
import time
from datetime import datetime
from threading import Thread
from flask import current_app
from app import db
from app.models import Application, ApplicationInstance

def check_status(host, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port or 80))
        sock.close()
        return result == 0
    except:
        return False

def background_status_check():
    """Background task to check all application statuses"""
    try:
        applications = Application.query.all()
        for app in applications:
            down_count = 0
            total_instances = len(app.instances)
            
            for instance in app.instances:
                instance.status = 'UP' if check_status(instance.host, instance.port) else 'DOWN'
                if instance.status == 'DOWN':
                    down_count += 1
                instance.last_checked = datetime.utcnow()
            
            app.status = 'UP' if down_count == 0 else f'DOWN ({down_count}/{total_instances})'
            app.last_checked = datetime.utcnow()
        
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Background status check error: {str(e)}")
        db.session.rollback()

def start_background_checker():
    """Start the background status checker thread"""
    def run_checker():
        while True:
            with current_app.app_context():
                background_status_check()
            time.sleep(30)  # Check every 30 seconds
    
    checker_thread = Thread(target=run_checker, daemon=True)
    checker_thread.start()
    return checker_thread
