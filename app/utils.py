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
        # Create a new session for HTTPS with proper verification
        with requests.Session() as session:
            try:
                response = session.get(url, timeout=5)
                if response.status_code >= 400:
                    details.append(f"WebUI returned error status {response.status_code}")
                    is_running = False
            except requests.exceptions.SSLError:
                # If HTTPS fails, try HTTP with a new session
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

def check_application_status(instance):
    """Check if an application instance is running by checking its host and port."""
    details = []
    is_running = True

    # Check if host is reachable
    try:
        ping_result = ping(instance.host, timeout=1)
        if ping_result is None or ping_result is False:
            details.append(f"Host {instance.host} is unreachable")
            is_running = False
    except Exception as e:
        details.append(f"Error pinging host {instance.host}: {str(e)}")
        is_running = False

    # If port is specified, check if it's open
    if instance.port and is_running:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((instance.host, instance.port))
            sock.close()
            
            if result != 0:
                details.append(f"Port {instance.port} is not open")
                is_running = False
        except Exception as e:
            details.append(f"Error checking port {instance.port}: {str(e)}")
            is_running = False

    if not details:
        details.append("All checks passed")

    return is_running, details

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

def get_shutdown_sequence(app, visited=None):
    """Get the sequence of applications that need to be shut down."""
    if visited is None:
        visited = set()
    
    if app.id in visited:
        return []
    
    visited.add(app.id)
    sequence = []
    
    # First get dependencies
    for dep in app.dependencies:
        if dep.dependency_type == 'shutdown_before':
            sequence.extend(get_shutdown_sequence(dep.application, visited))
    
    # Add current app if not already in sequence
    if app not in sequence:
        sequence.append(app)
    
    return sequence

def clean_csv_value(value):
    """Clean and validate a CSV value."""
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None

def map_csv_columns(headers):
    """Map CSV headers to expected column names."""
    column_mapping = {}
    expected_columns = {
        'name': ['name', 'application', 'app_name', 'application_name'],
        'team': ['team', 'team_name'],
        'host': ['host', 'hostname', 'server'],
        'port': ['port'],
        'webui_url': ['webui_url', 'web_url', 'url'],
        'db_host': ['db_host', 'database_host'],
        'shutdown_order': ['shutdown_order', 'order'],
        'dependencies': ['dependencies', 'depends_on']
    }
    
    for header in headers:
        header = header.strip().lower()
        for column, aliases in expected_columns.items():
            if header in aliases:
                column_mapping[column] = header
                break
    
    return column_mapping
