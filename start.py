#!/usr/bin/env python3
import os
import sys
import subprocess
import signal
import time
from pathlib import Path

def check_python_version():
    """Check if Python version is 3.8 or higher."""
    required_version = (3, 8)
    current_version = sys.version_info[:2]
    if current_version < required_version:
        print(f"Error: Python 3.8 or higher is required. Found version {sys.version}")
        sys.exit(1)

def check_port(port):
    """Check if a port is in use."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def check_env_file():
    """Check if .env file exists in the backend directory."""
    env_path = Path("backend/.env")
    if not env_path.exists():
        print("Warning: .env file not found in backend directory")
        return False
    return True

def start_services():
    """Start all services using the start_all.sh script."""
    # Get the absolute path to the start_all.sh script
    script_dir = Path(__file__).parent
    start_script = script_dir / "backend" / "start_all.sh"
    
    if not start_script.exists():
        print(f"Error: start_all.sh not found at {start_script}")
        sys.exit(1)
    
    # Make the script executable
    start_script.chmod(0o755)
    
    try:
        # Run the start_all.sh script
        process = subprocess.Popen(
            [str(start_script)],
            cwd=str(script_dir / "backend"),
            shell=True,
            preexec_fn=os.setsid  # Create a new process group
        )
        
        print("\nServices started successfully!")
        print("Backend running at http://localhost:8000")
        print("Frontend running at http://localhost:3000")
        print("\nPress Ctrl+C to stop all services...")
        
        # Wait for the process to complete
        process.wait()
        
    except KeyboardInterrupt:
        print("\nStopping services...")
        # Kill the process group
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        sys.exit(0)
    except Exception as e:
        print(f"Error starting services: {e}")
        sys.exit(1)

def main():
    """Main function to start all services."""
    print("Starting personal trainer AI assistant...")
    
    # Check Python version
    check_python_version()
    
    # Check if .env file exists
    check_env_file()
    
    # Check if ports are in use
    if check_port(8000):
        print("Error: Port 8000 is already in use")
        sys.exit(1)
    if check_port(3000):
        print("Error: Port 3000 is already in use")
        sys.exit(1)
    
    # Start all services
    start_services()

if __name__ == "__main__":
    main() 