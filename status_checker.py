#!/usr/bin/env python3
import logging
import socket
import sqlite3
import sys
import time
import json
import requests
import os
from datetime import datetime
from urllib.parse import urlparse
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('status_checker')

def check_port(host, port, timeout=5):
    """Check if a port is open on a host."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        return False

def check_webui(url, timeout=5):
    """Check if a WebUI URL is accessible."""
    if not url:
        return None
    try:
        response = requests.get(url, timeout=timeout, verify=False)
        return response.status_code == 200
    except Exception:
        return False

def check_instance_status(instance):
    """Check the status of an application instance."""
    details = []
    status = 'unknown'
    
    # Check port if specified
    if instance['port']:
        port_status = check_port(instance['host'], instance['port'])
        details.append(f"Port {instance['port']}: {'Open' if port_status else 'Closed'}")
        if port_status:
            status = 'running'
        else:
            status = 'stopped'
    
    # Check WebUI if specified
    if instance['webui_url']:
        webui_status = check_webui(instance['webui_url'])
        details.append(f"WebUI: {'Accessible' if webui_status else 'Not accessible'}")
        if webui_status is False:  # Only update if explicitly False (not None)
            status = 'error' if status == 'running' else 'stopped'
    
    return status, ' | '.join(details)

def update_instance_status(cursor, instance_id, status, details):
    """Update the status and details of an instance in the database."""
    try:
        cursor.execute("""
            UPDATE application_instance 
            SET status = ?, details = ?, last_checked = ? 
            WHERE id = ?
        """, (status, details, datetime.utcnow().isoformat(), instance_id))
    except Exception as e:
        logger.error(f"Error updating instance {instance_id}: {str(e)}")

def get_instances(cursor):
    """Get all application instances from the database."""
    cursor.execute("""
        SELECT id, host, port, webui_url, db_host 
        FROM application_instance
    """)
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def main():
    if len(sys.argv) != 2:
        print("Usage: status_checker.py <database_path>")
        sys.exit(1)
    
    db_path = os.path.abspath(sys.argv[1])
    logger.info(f"Status checker service started with database: {db_path}")
    
    if not os.path.exists(os.path.dirname(db_path)):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Create Flask app for database models
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db = SQLAlchemy(app)
    
    # Define models
    class ApplicationInstance(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
        host = db.Column(db.String(100), nullable=False)
        port = db.Column(db.Integer)
        webui_url = db.Column(db.String(200))
        db_host = db.Column(db.String(100))
        status = db.Column(db.String(20), default='unknown')
        details = db.Column(db.Text)
        last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    
    class Application(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
        instances = db.relationship('ApplicationInstance', backref='application', lazy=True)
    
    class Team(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), unique=True, nullable=False)
        applications = db.relationship('Application', backref='team', lazy=True)
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    while True:
        try:
            with app.app_context():
                instances = ApplicationInstance.query.all()
                logger.info(f"Checking status for {len(instances)} instances")
                
                for instance in instances:
                    try:
                        status, details = check_instance_status({
                            'host': instance.host,
                            'port': instance.port,
                            'webui_url': instance.webui_url
                        })
                        instance.status = status
                        instance.details = details
                        instance.last_checked = datetime.utcnow()
                    except Exception as e:
                        logger.error(f"Error checking instance {instance.id}: {str(e)}")
                        continue
                
                try:
                    db.session.commit()
                    logger.info("Successfully updated instance statuses")
                except Exception as e:
                    logger.error(f"Error committing status updates: {str(e)}")
                    db.session.rollback()
        
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
        
        time.sleep(30)  # Wait 30 seconds before next check

if __name__ == "__main__":
    main()
