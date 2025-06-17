import subprocess
import time
import requests
import pytest
import os
import signal
import sys

def test_basic_e2e():
    """Basic end-to-end test that verifies both frontend and backend start properly."""
    # Start the application using run.py
    process = subprocess.Popen(
        [sys.executable, "run.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    try:
        # Wait for backend to start
        max_attempts = 10
        for _ in range(max_attempts):
            try:
                response = requests.get("http://localhost:8000/api/health")
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                time.sleep(1)
        else:
            pytest.fail("Backend failed to start within expected time")
            
        # Wait for frontend to start
        max_attempts = 10
        for _ in range(max_attempts):
            try:
                response = requests.get("http://localhost:3000")
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                time.sleep(1)
        else:
            pytest.fail("Frontend failed to start within expected time")
            
    finally:
        # Create shutdown signal file to trigger graceful shutdown
        with open("shutdown.signal", "w") as f:
            f.write("")
            
        # Wait for processes to terminate
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            
        # Clean up shutdown signal file if it still exists
        if os.path.exists("shutdown.signal"):
            os.remove("shutdown.signal") 