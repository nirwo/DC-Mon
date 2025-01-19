#!/usr/bin/env python3
import os
import sys
import time
import json
import socket
import logging
import sqlite3
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('status_checker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('status_checker')

def check_port(host, port, timeout=2):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        logger.error(f"Error checking {host}:{port} - {str(e)}")
        return False

def check_webui(url, timeout=5):
    if not url:
        return None
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error checking WebUI {url} - {str(e)}")
        return False

def check_instance_status(instance):
    host = instance['host']
    port = instance['port']
    webui_url = instance['webui_url']
    
    port_status = check_port(host, port) if port else None
    webui_status = check_webui(webui_url) if webui_url else None
    
    status = 'unknown'
    details = []
    
    if port_status is not None:
        details.append(f"Port {'open' if port_status else 'closed'}")
        if port_status:
            status = 'running'
        else:
            status = 'stopped'
            
    if webui_status is not None:
        details.append(f"WebUI {'accessible' if webui_status else 'inaccessible'}")
        if status == 'unknown':
            status = 'running' if webui_status else 'stopped'
        elif status == 'running' and not webui_status:
            status = 'error'
            
    return {
        'id': instance['id'],
        'status': status,
        'details': details,
        'last_checked': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def update_instance_status(db_path, instance_id, status, details, last_checked):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE application_instance 
            SET status = ?, details = ?, last_checked = ? 
            WHERE id = ?
        ''', (status, json.dumps(details), last_checked, instance_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error updating database for instance {instance_id}: {str(e)}")

def get_instances(db_path):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, host, port, webui_url 
            FROM application_instance
        ''')
        instances = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return instances
    except Exception as e:
        logger.error(f"Error fetching instances: {str(e)}")
        return []

def main():
    if len(sys.argv) != 2:
        print("Usage: python status_checker.py /path/to/app.db")
        sys.exit(1)
        
    db_path = sys.argv[1]
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        sys.exit(1)
    
    logger.info("Status checker service started")
    
    while True:
        try:
            instances = get_instances(db_path)
            logger.info(f"Checking status for {len(instances)} instances")
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for instance in instances:
                    futures.append(executor.submit(check_instance_status, instance))
                
                for instance, future in zip(instances, futures):
                    try:
                        result = future.result()
                        update_instance_status(
                            db_path,
                            result['id'],
                            result['status'],
                            result['details'],
                            result['last_checked']
                        )
                    except Exception as e:
                        logger.error(f"Error processing instance {instance['id']}: {str(e)}")
            
            logger.info("Status check complete")
            time.sleep(30)  # Wait 30 seconds before next check
            
        except Exception as e:
            logger.error(f"Main loop error: {str(e)}")
            time.sleep(5)  # Wait 5 seconds on error before retrying

if __name__ == '__main__':
    main()
