import subprocess
import sys
import os
import signal
import time
import logging
from typing import Optional
import threading
import requests
import traceback

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the backend directory to sys.path if not already present
backend_path = os.path.join(os.path.dirname(__file__), "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
    logger.debug(f"Added {backend_path} to sys.path")

SHUTDOWN_SIGNAL_FILE = "shutdown.signal"

def kill_process_on_port(port: int) -> None:
    """Kill any process running on the specified port."""
    try:
        logger.debug(f"Checking for processes on port {port}")
        # Get all processes using the port
        cmd = f"lsof -i :{port} -t"
        pids = subprocess.check_output(cmd, shell=True).decode().strip().split('\n')
        logger.debug(f"Found processes on port {port}: {pids}")
        
        for pid in pids:
            if pid:  # Skip empty strings
                try:
                    pid = int(pid)
                    # Skip if it's our own process or our parent
                    if pid != os.getpid() and pid != os.getppid():
                        logger.debug(f"Attempting to kill process {pid} on port {port}")
                        os.kill(pid, signal.SIGTERM)
                        logger.info(f"Killed process {pid} on port {port}")
                except (ValueError, ProcessLookupError) as e:
                    logger.warning(f"Failed to kill process {pid}: {str(e)}")
                    continue
    except subprocess.CalledProcessError:
        logger.debug(f"No processes found on port {port}")
    except Exception as e:
        logger.error(f"Error killing processes on port {port}: {str(e)}")
        logger.debug(traceback.format_exc())

def run_backend() -> Optional[subprocess.Popen]:
    """Run the backend server as a module from the project root."""
    try:
        logger.debug("Starting backend server setup...")
        # Kill any existing process on port 8000
        kill_process_on_port(8000)
        
        # Start the backend server as a module from the project root
        cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
        logger.debug(f"Starting backend with command: {' '.join(cmd)}")
        
        backend_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=os.path.dirname(__file__)  # Run from project root
        )
        logger.info(f"Started Backend process with PID {backend_process.pid}")
        
        # Check if process started successfully
        if backend_process.poll() is not None:
            logger.error(f"Backend process failed to start. Return code: {backend_process.poll()}")
            return None
            
        return backend_process
    except Exception as e:
        logger.error(f"Failed to start backend: {str(e)}")
        logger.debug(traceback.format_exc())
        return None

def run_frontend() -> Optional[subprocess.Popen]:
    """Run the frontend development server."""
    try:
        logger.debug("Starting frontend server setup...")
        # Kill any existing process on port 3000
        kill_process_on_port(3000)
        
        # Start the frontend server
        frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
        logger.debug(f"Starting frontend from directory: {frontend_dir}")
        
        frontend_process = subprocess.Popen(
            ["npm", "start"],
            cwd=frontend_dir,  # Use absolute path
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        logger.info(f"Started Frontend process with PID {frontend_process.pid}")
        
        # Check if process started successfully
        if frontend_process.poll() is not None:
            logger.error(f"Frontend process failed to start. Return code: {frontend_process.poll()}")
            return None
            
        return frontend_process
    except Exception as e:
        logger.error(f"Failed to start frontend: {str(e)}")
        logger.debug(traceback.format_exc())
        return None

def shutdown_watcher(backend_process, frontend_process):
    logger.debug("Starting shutdown watcher thread")
    while True:
        if os.path.exists(SHUTDOWN_SIGNAL_FILE):
            logger.info("Shutdown signal received. Shutting down servers...")
            if backend_process:
                logger.debug("Terminating backend process")
                backend_process.terminate()
            if frontend_process:
                logger.debug("Terminating frontend process")
                frontend_process.terminate()
            os.remove(SHUTDOWN_SIGNAL_FILE)
            logger.info("All processes cleaned up (shutdown signal)")
            os._exit(0)
        time.sleep(1)

def main():
    """Main function to run both frontend and backend servers."""
    try:
        # Ensure we're in the project root
        os.chdir(os.path.dirname(__file__))
        logger.info(f"Working directory set to: {os.getcwd()}")

        # Install the backend package in development mode
        logger.info("Installing backend package in development mode (from main)...")
        install_process = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "backend"],
            capture_output=True,
            text=True
        )
        if install_process.returncode != 0:
            logger.error(f"Failed to install backend package: {install_process.stderr}")
            logger.debug(f"Install process stdout: {install_process.stdout}")
            return
        logger.info("Backend package installed successfully (from main)")
        
        # Start backend
        logger.info("Starting backend server...")
        backend_process = run_backend()
        if not backend_process:
            logger.error("Failed to start backend server")
            return

        # Wait a moment to ensure backend is up
        logger.debug("Waiting for backend to start...")
        time.sleep(2)
        
        # Verify backend is running
        try:
            logger.debug("Checking backend health...")
            response = requests.get("http://localhost:8000/api/health")
            if response.status_code != 200:
                logger.error(f"Backend health check failed with status {response.status_code}")
                logger.debug(f"Health check response: {response.text}")
                backend_process.terminate()
                return
            logger.info("Backend health check passed")
        except Exception as e:
            logger.error(f"Backend health check failed: {str(e)}")
            logger.debug(traceback.format_exc())
            backend_process.terminate()
            return

        # Start frontend
        logger.info("Starting frontend server...")
        frontend_process = run_frontend()
        if not frontend_process:
            logger.error("Failed to start frontend server")
            backend_process.terminate()
            return

        # Start shutdown watcher thread
        logger.debug("Starting shutdown watcher thread")
        watcher_thread = threading.Thread(target=shutdown_watcher, args=(backend_process, frontend_process), daemon=True)
        watcher_thread.start()

        # Stream output from both processes
        logger.debug("Starting to stream process output")
        while True:
            # Print all available backend output immediately
            backend_line = backend_process.stdout.readline()
            while backend_line:
                print(f"[BACKEND] {backend_line.strip()}")
                backend_line = backend_process.stdout.readline()

            # Print all available frontend output
            frontend_line = frontend_process.stdout.readline()
            while frontend_line:
                print(f"[FRONTEND] {frontend_line.strip()}")
                frontend_line = frontend_process.stdout.readline()

            # Check if either process has ended
            if backend_process.poll() is not None:
                logger.error(f"Backend process ended unexpectedly with return code {backend_process.poll()}")
                break
            if frontend_process.poll() is not None:
                logger.error(f"Frontend process ended unexpectedly with return code {frontend_process.poll()}")
                break

            # Small sleep to prevent CPU spinning
            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.debug(traceback.format_exc())
    finally:
        # Clean up processes
        if 'backend_process' in locals() and backend_process:
            logger.info("Terminating backend process...")
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Backend process did not terminate gracefully, forcing...")
                backend_process.kill()
                
        if 'frontend_process' in locals() and frontend_process:
            logger.info("Terminating frontend process...")
            frontend_process.terminate()
            try:
                frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Frontend process did not terminate gracefully, forcing...")
                frontend_process.kill()
                
        logger.info("All processes cleaned up")

if __name__ == "__main__":
    main() 