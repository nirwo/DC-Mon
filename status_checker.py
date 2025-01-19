#!/usr/bin/env python3
import logging
import socket
import sqlite3
import sys
import time
import json
import requests
from datetime import datetime
from urllib.parse import urlparse

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
        logger.error(f"Error updating instance {instance_id}: {e}")

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
    
    db_path = sys.argv[1]
    logger.info("Status checker service started")
    
    while True:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            instances = get_instances(cursor)
            logger.info(f"Checking status for {len(instances)} instances")
            
            for instance in instances:
                try:
                    status, details = check_instance_status(instance)
                    update_instance_status(cursor, instance['id'], status, details)
                except Exception as e:
                    logger.error(f"Error checking instance {instance['id']}: {e}")
            
            conn.commit()
            logger.info("Status check complete")
            
        except Exception as e:
            logger.error(f"Database error: {e}")
        
        finally:
            if 'conn' in locals():
                conn.close()
        
        time.sleep(30)  # Wait 30 seconds before next check

if __name__ == "__main__":
    main()
