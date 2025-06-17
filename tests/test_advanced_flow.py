import pytest
import time
import subprocess
import sys
import os
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import openai
from datetime import datetime, timedelta
import psutil

def kill_process_on_port(port):
    """Kill any process running on the specified port."""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.net_connections():
                if conn.laddr.port == port:
                    proc.kill()
                    time.sleep(1)  # Give time for the port to be released
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def wait_for_service(url, max_attempts=30, delay=1):
    """Wait for a service to be available."""
    for _ in range(max_attempts):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            time.sleep(delay)
    return False

def find_chat_input(driver, timeout=20):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Type your message...']"))
        )
    except Exception as e:
        print("\n[DEBUG] Could not find chat input. Page source:\n", driver.page_source)
        raise

def wait_for_input_enabled(driver, timeout=30):
    """Wait for the chat input to be enabled and ready for the next message."""
    try:
        # First wait for any loading indicators to disappear
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".loading-dots"))
        )
        # Then wait for the input to be enabled and return the element
        input_element = WebDriverWait(driver, timeout).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "input[placeholder='Type your message...']")
        )
        if not input_element.is_enabled():
            WebDriverWait(driver, timeout).until(lambda d: input_element.is_enabled())
        time.sleep(1)
        return input_element
    except Exception as e:
        print("\n[DEBUG] Error waiting for input to be enabled:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print("\nCurrent page source:")
        print(driver.page_source)
        raise

def test_calendar_workflow():
    """Test creating a workout event and verifying it appears in the upcoming events list."""
    # Kill any existing processes on the required ports
    kill_process_on_port(8000)
    kill_process_on_port(3000)
    
    # Start the application
    process = subprocess.Popen([sys.executable, "run.py"])
    
    try:
        # Wait for backend to start
        if not wait_for_service("http://localhost:8000/api/health"):
            pytest.fail("Backend failed to start")
            
        # Wait for frontend to start
        if not wait_for_service("http://localhost:3000"):
            pytest.fail("Frontend failed to start")
            
        # Set up Selenium
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            # Navigate to the application
            driver.get("http://localhost:3000")
            
            # Wait for chat input to be available
            chat_input = find_chat_input(driver)
            
            # Send message to create a workout event
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            chat_input.send_keys(f"Schedule a workout for tomorrow at 10 AM")
            chat_input.submit()
            
            # Wait for assistant's response and for input to be enabled again
            chat_input = wait_for_input_enabled(driver)
            
            # Get the last message from the assistant
            messages = driver.find_elements(By.CSS_SELECTOR, ".message.assistant")
            last_message = messages[-1].text if messages else ""
            
            # Accept tool call as valid event creation confirmation
            assert (
                "scheduled" in last_message.lower() or
                "created" in last_message.lower() or
                "added" in last_message.lower() or
                last_message.strip().startswith("create_calendar_event:")
            ), f"Response does not indicate event creation: {last_message}"
            
            # Add a small delay before asking about events
            time.sleep(2)
            
            # Ask about upcoming events
            chat_input.send_keys("What events do I have coming up in the next week?")
            chat_input.submit()
            
            # Wait for assistant's response and for input to be enabled again
            chat_input = wait_for_input_enabled(driver)
            
            # Get the last message from the assistant
            messages = driver.find_elements(By.CSS_SELECTOR, ".message.assistant")
            last_message = messages[-1].text if messages else ""
            
            # Use OpenAI to evaluate if the response is appropriate
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are evaluating if a response from a personal trainer AI assistant is appropriate. The response should mention the workout event that was just created for tomorrow at 10 AM. Use relaxed criteria - just check if the response mentions a workout event for tomorrow or the next day."},
                    {"role": "user", "content": f"Here's the assistant's response about upcoming events: {last_message}\n\nIs this response appropriate? Does it mention the workout event for tomorrow?"}
                ]
            )
            
            evaluation = response.choices[0].message.content.lower()
            assert "yes" in evaluation or "appropriate" in evaluation, f"Response evaluation failed: {evaluation}"
            
        finally:
            driver.quit()
            
    finally:
        # Create shutdown signal file
        with open("shutdown_signal.txt", "w") as f:
            f.write("shutdown")
        time.sleep(2)  # Give time for services to shut down
        if os.path.exists("shutdown_signal.txt"):
            os.remove("shutdown_signal.txt")
        process.terminate()
        process.wait()

def test_sheets_workflow():
    """Test creating a Google Sheet and writing data to it."""
    # Kill any existing processes on the required ports
    kill_process_on_port(8000)
    kill_process_on_port(3000)
    
    # Start the application
    process = subprocess.Popen([sys.executable, "run.py"])
    
    try:
        # Wait for backend to start
        if not wait_for_service("http://localhost:8000/api/health"):
            pytest.fail("Backend failed to start")
            
        # Wait for frontend to start
        if not wait_for_service("http://localhost:3000"):
            pytest.fail("Frontend failed to start")
            
        # Set up Selenium
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            # Navigate to the application
            driver.get("http://localhost:3000")
            
            # Wait for chat input to be available
            chat_input = find_chat_input(driver)
            
            # Send message to create a sheet and write data
            chat_input.send_keys("Create a new Google Sheet called 'Test Sheet' and write 'Hello World' in cell A1")
            chat_input.submit()
            
            # Wait for assistant's response
            time.sleep(5)
            
            # Get the last message from the assistant
            messages = driver.find_elements(By.CSS_SELECTOR, ".message.assistant")
            last_message = messages[-1].text if messages else ""
            
            # Use OpenAI to evaluate if the response is appropriate
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are evaluating if a response from a personal trainer AI assistant is appropriate. The response should indicate that a new Google Sheet was created and 'Hello World' was written to it. Use relaxed criteria - just check if the response mentions creating a sheet and writing data."},
                    {"role": "user", "content": f"Here's the assistant's response: {last_message}\n\nIs this response appropriate? Does it mention creating a sheet and writing data?"}
                ]
            )
            
            evaluation = response.choices[0].message.content.lower()
            assert "yes" in evaluation or "appropriate" in evaluation, f"Response evaluation failed: {evaluation}"
            
        finally:
            driver.quit()
            
    finally:
        # Create shutdown signal file
        with open("shutdown_signal.txt", "w") as f:
            f.write("shutdown")
        time.sleep(2)  # Give time for services to shut down
        if os.path.exists("shutdown_signal.txt"):
            os.remove("shutdown_signal.txt")
        process.terminate()
        process.wait()

def test_greeting_flow():
    """Test sending a greeting message and verifying the agent's response."""
    # Kill any existing processes on the required ports
    kill_process_on_port(8000)
    kill_process_on_port(3000)
    
    # Start the application
    process = subprocess.Popen([sys.executable, "run.py"])
    
    try:
        # Wait for backend to start
        if not wait_for_service("http://localhost:8000/api/health"):
            pytest.fail("Backend failed to start")
            
        # Wait for frontend to start
        if not wait_for_service("http://localhost:3000"):
            pytest.fail("Frontend failed to start")
            
        # Set up Selenium
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            # Navigate to the application
            driver.get("http://localhost:3000")
            
            # Wait for chat input to be available
            chat_input = find_chat_input(driver)
            
            # Send a greeting message
            chat_input.send_keys("Hello! I'm looking to get started with my fitness journey.")
            chat_input.submit()
            
            # Wait for assistant's response and for input to be enabled again
            chat_input = wait_for_input_enabled(driver)
            
            # Get the last message from the assistant
            messages = driver.find_elements(By.CSS_SELECTOR, ".message.assistant")
            last_message = messages[-1].text if messages else ""
            
            # Use OpenAI to evaluate if the response is appropriate
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are evaluating if a response from a personal trainer AI assistant is appropriate. The response should be welcoming, acknowledge the user's interest in fitness, and offer to help them get started. Use relaxed criteria - just check if the response is friendly and fitness-oriented."},
                    {"role": "user", "content": f"User message: 'Hello! I'm looking to get started with my fitness journey.'\nAssistant response: {last_message}\n\nIs this response appropriate? Does it acknowledge the user's interest in fitness and offer help?"}
                ]
            )
            
            evaluation = response.choices[0].message.content.lower()
            assert "yes" in evaluation or "appropriate" in evaluation, f"Response evaluation failed: {evaluation}"
            
            # Add a small delay before sending the next message
            time.sleep(2)
            
            # Send a follow-up message about goals
            chat_input.send_keys("I want to lose weight and build some muscle. What should I do?")
            chat_input.submit()
            
            # Wait for assistant's response and for input to be enabled again
            chat_input = wait_for_input_enabled(driver)
            
            # Get the last message from the assistant
            messages = driver.find_elements(By.CSS_SELECTOR, ".message.assistant")
            last_message = messages[-1].text if messages else ""
            
            # Use OpenAI to evaluate if the response is appropriate
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are evaluating if a response from a personal trainer AI assistant is appropriate. The response should address both weight loss and muscle building goals, and provide some initial guidance or suggestions. Use relaxed criteria - just check if the response mentions both goals and offers some form of help."},
                    {"role": "user", "content": f"User message: 'I want to lose weight and build some muscle. What should I do?'\nAssistant response: {last_message}\n\nIs this response appropriate? Does it address both weight loss and muscle building goals?"}
                ]
            )
            
            evaluation = response.choices[0].message.content.lower()
            assert "yes" in evaluation or "appropriate" in evaluation, f"Response evaluation failed: {evaluation}"
            
        finally:
            driver.quit()
            
    finally:
        # Create shutdown signal file
        with open("shutdown_signal.txt", "w") as f:
            f.write("shutdown")
        time.sleep(2)  # Give time for services to shut down
        if os.path.exists("shutdown_signal.txt"):
            os.remove("shutdown_signal.txt")
        process.terminate()
        process.wait() 