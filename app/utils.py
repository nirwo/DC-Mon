import requests
from datetime import datetime
import socket
from typing import Dict, Optional

def check_port(host: str, port: int, timeout: int = 2) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            return result == 0
    except:
        return False

def check_webui(url: str, timeout: int = 5) -> bool:
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except:
        return False

def check_db_connection(host: str) -> bool:
    # This is a simplified check - in real implementation,
    # you'd want to check specific database types
    try:
        host, port = host.split(':')
        return check_port(host, int(port))
    except:
        return False

def get_application_status(app) -> Dict[str, any]:
    status = {
        'is_running': False,
        'webui_status': False,
        'db_status': False,
        'last_checked': datetime.utcnow(),
        'details': []
    }
    
    # Check main application port
    if app.port:
        status['is_running'] = check_port(app.host, app.port)
        status['details'].append(f"Application {'running' if status['is_running'] else 'not running'} on {app.host}:{app.port}")
    
    # Check WebUI if configured
    if app.webui_url:
        status['webui_status'] = check_webui(app.webui_url)
        status['details'].append(f"WebUI {'up' if status['webui_status'] else 'down'} at {app.webui_url}")
    
    # Check database if configured
    if app.db_host:
        status['db_status'] = check_db_connection(app.db_host)
        status['details'].append(f"Database {'connected' if status['db_status'] else 'disconnected'} at {app.db_host}")
    
    return status

def get_shutdown_sequence(app, visited=None) -> list:
    if visited is None:
        visited = set()
    
    if app.id in visited:
        return []
    
    visited.add(app.id)
    sequence = []
    
    # Get all dependencies that need to be shut down before this app
    for dep in app.dependencies:
        if dep.dependency_type == 'shutdown_before':
            sequence.extend(get_shutdown_sequence(dep.application, visited))
    
    sequence.append(app)
    
    # Get all dependencies that need to be shut down after this app
    for dep in app.dependencies:
        if dep.dependency_type == 'shutdown_after':
            sequence.extend(get_shutdown_sequence(dep.application, visited))
    
    return sequence
