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

def test_basic_conversation():
    """Test basic conversation flow with a greeting message."""
    # Start the application
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
            
        # Set up Chrome options for headless mode
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Initialize the Chrome driver
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            # Navigate to the application
            driver.get("http://localhost:3000")
            
            # Wait for the chat input to be present
            chat_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "chat-input"))
            )
            
            # Send a greeting message
            chat_input.send_keys("Hello! How are you today?")
            chat_input.submit()
            
            # Wait for the response (up to 10 seconds)
            response_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "message.assistant"))
            )
            
            # Get the response text
            response_text = response_element.text.strip()
            
            # Verify the response is not empty and doesn't contain error messages
            assert response_text, "Response should not be empty"
            assert "error" not in response_text.lower(), "Response should not contain error messages"
            
            # Use OpenAI to evaluate if the response is appropriate for a greeting
            client = openai.OpenAI()
            evaluation = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are evaluating if a response to a greeting is appropriate. Respond with 'APPROPRIATE' or 'INAPPROPRIATE' followed by a brief explanation."},
                    {"role": "user", "content": f"User greeting: 'Hello! How are you today?'\nAgent response: '{response_text}'\nIs this an appropriate response to a greeting?"}
                ]
            )
            
            evaluation_result = evaluation.choices[0].message.content
            assert "APPROPRIATE" in evaluation_result, f"Response was not appropriate for a greeting: {evaluation_result}"
            
        finally:
            driver.quit()
            
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