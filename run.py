import os
import sys
import socket
from app import create_app

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def find_free_port(start_port=5001, max_attempts=10):
    for port in range(start_port, start_port + max_attempts):
        if not is_port_in_use(port):
            return port
    return None

if __name__ == '__main__':
    try:
        port = find_free_port()
        if not port:
            print("No free ports found in range 5001-5010")
            sys.exit(1)
            
        app = create_app()
        print(f" * Starting server on port {port}")
        app.run(debug=True, port=port, threaded=True)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)
