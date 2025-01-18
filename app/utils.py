import requests
from ping3 import ping
from urllib.parse import urlparse
import socket
from datetime import datetime
from typing import Dict, Optional, Any

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

def check_host_status(host, port=None):
    """Check if a host is reachable via ICMP ping and optionally TCP port."""
    details = []
    is_running = True
    
    # Try ICMP ping
    try:
        response_time = ping(host, timeout=1)
        if response_time is None or response_time is False:
            details.append(f"Host {host} is not responding to ping")
            is_running = False
    except Exception as e:
        details.append(f"Error pinging {host}: {str(e)}")
        is_running = False
    
    # Check TCP port if specified
    if port:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, int(port)))
            sock.close()
            
            if result != 0:
                details.append(f"Port {port} is not open on {host}")
                is_running = False
        except Exception as e:
            details.append(f"Error checking port {port} on {host}: {str(e)}")
            is_running = False
    
    return is_running, details

def check_webui_status(url):
    """Check if a WebUI URL is accessible via HTTP GET."""
    if not url:
        return True, []
        
    details = []
    is_running = True
    
    try:
        response = requests.get(url, timeout=5, verify=False)
        if response.status_code >= 400:
            details.append(f"WebUI returned error status {response.status_code}")
            is_running = False
    except requests.exceptions.SSLError:
        # Try without HTTPS if SSL fails
        http_url = url.replace('https://', 'http://')
        try:
            response = requests.get(http_url, timeout=5)
            if response.status_code >= 400:
                details.append(f"WebUI returned error status {response.status_code}")
                is_running = False
        except Exception as e:
            details.append(f"WebUI is not accessible: {str(e)}")
            is_running = False
    except Exception as e:
        details.append(f"WebUI is not accessible: {str(e)}")
        is_running = False
    
    return is_running, details

def check_db_status(db_host):
    """Check if a database host is reachable."""
    if not db_host:
        return True, []
        
    # Extract host and port from db_host
    try:
        if ':' in db_host:
            host, port = db_host.split(':')
            port = int(port)
        else:
            host = db_host
            port = 5432  # Default PostgreSQL port
            
        return check_host_status(host, port)
    except Exception as e:
        return False, [f"Invalid database host format: {str(e)}"]

def check_application_status(app):
    """Check the status of an application by checking host, WebUI, and database."""
    all_details = []
    is_running = True
    
    # Check main application host
    host_running, host_details = check_host_status(app.host, app.port)
    if not host_running:
        is_running = False
        all_details.extend(host_details)
    
    # Check WebUI if configured
    if app.webui_url:
        webui_running, webui_details = check_webui_status(app.webui_url)
        if not webui_running:
            is_running = False
            all_details.extend(webui_details)
    
    # Check database if configured
    if app.db_host:
        db_running, db_details = check_db_status(app.db_host)
        if not db_running:
            is_running = False
            all_details.extend(db_details)
    
    return 'running' if is_running else 'stopped', all_details

def get_application_status(app) -> Dict[str, Any]:
    status = {
        'is_running': False,
        'webui_status': False,
        'db_status': False,
        'last_checked': datetime.utcnow(),
        'details': []
    }
    
    # Check main application port
    if app.port:
        status['is_running'], status['details'] = check_application_status(app)
    
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
