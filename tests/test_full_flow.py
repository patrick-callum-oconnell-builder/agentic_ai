import subprocess
import time
import httpx
import pytest
import logging
import os
import sys
import threading
import queue
import json
import signal
import psutil
import asyncio
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def kill_process_tree(pid):
    """Kill a process and all its children."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.terminate()
        parent.terminate()
        gone, still_alive = psutil.wait_procs(children + [parent], timeout=3)
        for p in still_alive:
            p.kill()
    except psutil.NoSuchProcess:
        pass

async def wait_for_server(url: str, max_retries: int = 60, retry_interval: float = 1.0) -> bool:
    """Wait for the server to be ready by checking the health endpoint."""
    for i in range(max_retries):
        try:
            logger.debug(f"Attempting to connect to {url} (attempt {i + 1}/{max_retries})")
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    logger.info(f"Server is ready at {url}")
                    return True
        except httpx.ConnectError as e:
            logger.debug(f"Connection error on attempt {i + 1}/{max_retries}: {str(e)}")
            await asyncio.sleep(retry_interval)
        except httpx.TimeoutException as e:
            logger.debug(f"Timeout on attempt {i + 1}/{max_retries}: {str(e)}")
            await asyncio.sleep(retry_interval)
        except Exception as e:
            logger.debug(f"Unexpected error on attempt {i + 1}/{max_retries}: {str(e)}")
            await asyncio.sleep(retry_interval)
    return False

def read_output(process, output_queue):
    """Read process output and put it in a queue."""
    for line in iter(process.stdout.readline, ''):
        output_queue.put(line.strip())
    process.stdout.close()

async def run_with_timeout(coro, timeout_seconds: float):
    """Run a coroutine with a timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.error(f"Operation timed out after {timeout_seconds} seconds")
        raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds")

@pytest.mark.asyncio
async def test_full_flow_greeting():
    """Test the full flow of running both frontend and backend and sending a greeting."""
    async def run_test():
        logger.info("Starting servers...")
        process = None
        output_queue = None
        try:
            # Get the project root directory (one level up from the test file)
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            os.chdir(project_root)
            logger.info(f"Working directory set to: {os.getcwd()}")

            # Install the backend package in development mode
            logger.info("Installing backend package in development mode...")
            install_process = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", "."],
                capture_output=True,
                text=True
            )
            if install_process.returncode != 0:
                logger.error(f"Failed to install backend package: {install_process.stderr}")
                logger.debug(f"Install process stdout: {install_process.stdout}")
                raise RuntimeError("Failed to install backend package")

            process = subprocess.Popen(
                ["python", "run.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Create a queue for process output
            output_queue = queue.Queue()
            
            # Start a thread to read the output
            output_thread = threading.Thread(target=read_output, args=(process, output_queue))
            output_thread.daemon = True
            output_thread.start()
            
            # Print any output while waiting for server
            logger.info("Waiting for backend server to be ready...")
            server_ready = await wait_for_server("http://localhost:8000/api/health")
            
            if not server_ready:
                raise TimeoutError("Server failed to start within timeout period")
            
            # Wait a bit for the agent to initialize
            await asyncio.sleep(2)
            
            logger.info("Sending greeting to agent...")
            async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
                # First, check if the agent is ready
                try:
                    health_response = await client.get("/api/health")
                    assert health_response.status_code == 200, "Health check failed"
                except Exception as e:
                    logger.error(f"Health check failed: {str(e)}")
                    raise
                
                # Send the greeting
                payload = {"messages": [{"role": "user", "content": "Hi, how are you?"}]}
                try:
                    response = await client.post("/api/chat", json=payload)
                    await asyncio.sleep(1)  # Allow backend logs to flush
                    # Print all backend output after the chat request
                    if output_queue:
                        try:
                            while True:
                                line = output_queue.get_nowait()
                                print(f"Final server output: {line}")
                        except queue.Empty:
                            pass
                    if response.status_code != 200:
                        error_detail = response.text
                        logger.error(f"Error response from server: {error_detail}")
                        try:
                            error_json = response.json()
                            logger.error(f"Error JSON: {json.dumps(error_json, indent=2)}")
                        except:
                            pass
                    assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
                    data = response.json()
                    agent_response = data.get("response", "")
                    logger.info(f"Agent response: {agent_response}")
                    assert isinstance(agent_response, str)
                    assert len(agent_response) > 0
                    assert "error" not in agent_response.lower(), "Response should not contain the word 'error'"
                except Exception as e:
                    logger.error(f"Error during chat request: {str(e)}")
                    raise
        finally:
            logger.info("Terminating servers...")
            if process:
                try:
                    # Kill the entire process group
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("Process did not terminate gracefully, forcing...")
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    process.wait()
                except Exception as e:
                    logger.error(f"Error terminating process: {str(e)}")
                    # Fallback to psutil if os.killpg fails
                    kill_process_tree(process.pid)
            
            # Print any remaining output
            if output_queue:
                try:
                    while True:
                        line = output_queue.get_nowait()
                        print(f"Final server output: {line}")
                except queue.Empty:
                    pass

    # Run the test with a 60-second timeout
    await run_with_timeout(run_test(), 60.0)

@pytest.mark.asyncio
async def test_backend_health():
    """Test starting only the backend server and hitting the /api/health endpoint."""
    logger.info("Starting backend server only...")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    try:
        logger.info("Waiting for backend server to be ready...")
        if not wait_for_server("http://localhost:8000/api/health"):
            logger.error("Backend server failed to start")
            raise Exception("Backend server failed to start")
        logger.info("Backend server is up. Hitting /api/health endpoint...")
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            response = await client.get("/api/health")
            assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
            data = response.json()
            logger.info(f"Health endpoint response: {data}")
            assert data.get("status") == "healthy"
    finally:
        logger.info("Terminating backend server...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Process did not terminate gracefully, forcing...")
            process.kill()
            process.wait()
        output = process.stdout.read()
        if output:
            logger.debug("Backend server output:")
            for line in output.splitlines():
                logger.debug(f"  {line}") 