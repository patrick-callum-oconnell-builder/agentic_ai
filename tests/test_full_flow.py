import subprocess
import time
import os
import sys
import signal
import pytest
import httpx
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Helper to start a process
def start_process(cmd, cwd=None):
    print(f"Starting process: {' '.join(cmd)} in {cwd or os.getcwd()}")
    return subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, preexec_fn=os.setsid, text=True)

# Helper to stop a process
def stop_process(proc):
    if proc:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

# Wait for a server to be ready
def wait_for_server(url, timeout=60, proc=None):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(url, timeout=2)
            if r.status_code == 200:
                print(f"Server ready at {url}")
                return True
        except Exception:
            pass
        # Print process output if available
        if proc and proc.stdout:
            try:
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    print(f"[proc output] {line.strip()}")
            except Exception:
                pass
        time.sleep(1)
    print(f"Timeout waiting for {url}")
    return False

@pytest.mark.asyncio
async def test_full_flow_ui():
    import asyncio
    try:
        await asyncio.wait_for(_test_full_flow_ui(), timeout=60)
    except asyncio.TimeoutError:
        assert False, "Test timed out after 60 seconds"

def print_proc_output(proc, label):
    if proc and proc.stdout:
        print(f"--- {label} output ---")
        try:
            for line in proc.stdout:
                print(line.strip())
        except Exception:
            pass
        print(f"--- end {label} output ---")

async def _test_full_flow_ui():
    backend_proc = None
    frontend_proc = None
    driver = None
    try:
        print("[DEBUG] Starting backend server...")
        backend_proc = start_process([sys.executable, "run.py"], cwd=os.path.dirname(os.path.abspath(__file__)) + "/..")
        if not wait_for_server("http://localhost:8000/api/health", proc=backend_proc):
            print_proc_output(backend_proc, "backend")
            assert False, "Backend did not start"

        print("[DEBUG] Starting frontend server...")
        frontend_proc = start_process(["npm", "run", "start"], cwd="frontend")
        if not wait_for_server("http://localhost:3000", proc=frontend_proc):
            print_proc_output(frontend_proc, "frontend")
            assert False, "Frontend did not start"

        print("[DEBUG] Starting Selenium ChromeDriver...")
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("http://localhost:3000")

        print("[DEBUG] Waiting for input box...")
        input_box = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "input"))
        )
        print("[DEBUG] Sending message to agent...")
        input_box.send_keys("Hello, agent!" + Keys.RETURN)

        print("[DEBUG] Waiting for agent response in UI...")
        response_elem = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".assistant-message"))
        )
        response_text = response_elem.text.strip()
        print(f"[DEBUG] Agent response: {response_text}")
        assert response_text, "No response from agent"
        assert "error" not in response_text.lower(), f"Agent response contains error: {response_text}"
    finally:
        if driver:
            driver.quit()
        stop_process(frontend_proc)
        stop_process(backend_proc) 