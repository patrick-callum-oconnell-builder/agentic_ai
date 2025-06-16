import os
import sys
import pytest
import json
import re
from dotenv import load_dotenv
from backend.agent import PersonalTrainerAgent
from backend.google_services.maps import GoogleMapsService
from backend.google_services.calendar import GoogleCalendarService
from backend.google_services.gmail import GoogleGmailService
from backend.google_services.tasks import GoogleTasksService
from backend.google_services.drive import GoogleDriveService
from backend.google_services.sheets import GoogleSheetsService
from langchain_core.messages import HumanMessage

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) )

# Load environment variables
load_dotenv()

@pytest.fixture
def agent():
    load_dotenv()
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        pytest.skip("Missing required environment variable: GOOGLE_MAPS_API_KEY")
    
    # Initialize services
    calendar_service = GoogleCalendarService()
    gmail_service = GoogleGmailService()
    tasks_service = GoogleTasksService()
    drive_service = GoogleDriveService()
    sheets_service = GoogleSheetsService()
    maps_service = GoogleMapsService(api_key=api_key)
    
    # Authenticate services
    calendar_service.authenticate()
    gmail_service.authenticate()
    tasks_service.authenticate()
    drive_service.authenticate()
    sheets_service.authenticate()
    maps_service.authenticate()
    
    # Create and return the agent
    return PersonalTrainerAgent(
        calendar_service=calendar_service,
        gmail_service=gmail_service,
        tasks_service=tasks_service,
        drive_service=drive_service,
        sheets_service=sheets_service,
        maps_service=maps_service
    )

@pytest.mark.asyncio
async def test_find_nearby_workout_locations(agent):
    await agent.async_init()
    messages = [
        HumanMessage(content="Find me workout locations near 1 Infinite Loop, Cupertino, CA")
    ]
    response = await agent.process_messages(messages)
    print(f"Agent final response: {response}")
    # Check the last non-empty message
    if isinstance(response, str):
        lines = [msg.strip() for msg in response.split('\n') if msg.strip()]
        final_message = lines[-1] if lines else ""
    elif isinstance(response, list):
        final_message = response[-1] if response else ""
    else:
        final_message = str(response)
    assert final_message is not None
    assert isinstance(final_message, str)
    assert "Cupertino" in final_message or "workout" in final_message.lower()

@pytest.mark.asyncio
async def test_maps_tool_call(agent):
    await agent.async_init()
    messages = [
        HumanMessage(content="Find me workout locations near 1 Infinite Loop, Cupertino, CA")
    ]
    response = await agent.process_messages(messages)
    # If response is a string, try to extract the output field if present
    if isinstance(response, str):
        # Try to find a plausible location (address or gym name)
        location_pattern = re.compile(r"\d+\s+\w+\s+\w+|gym|fitness|YMCA|Pilates|Yoga|location", re.IGNORECASE)
        assert location_pattern.search(response), f"Response does not contain plausible location info: {response}"
    elif isinstance(response, dict):
        output = response.get('output', '')
        location_pattern = re.compile(r"\d+\s+\w+\s+\w+|gym|fitness|YMCA|Pilates|Yoga|location", re.IGNORECASE)
        assert location_pattern.search(output), f"Output does not contain plausible location info: {output}"
    else:
        assert False, f"Unexpected response type: {type(response)}"

@pytest.mark.asyncio
async def test_maps_tool_result(agent):
    await agent.async_init()
    # Directly call the tool with a JSON string to test LLM unpacking
    tool_input = json.dumps({
        'origin': '1 Infinite Loop, Cupertino, CA',
        'destination': 'Cupertino, CA'
    })
    result = await agent._execute_tool('get_directions', tool_input)
    print(f"Direct tool result: {result}")
    assert result is not None
    assert isinstance(result, str)
    assert len(result.strip()) > 0

if __name__ == '__main__':
    pytest.main() 