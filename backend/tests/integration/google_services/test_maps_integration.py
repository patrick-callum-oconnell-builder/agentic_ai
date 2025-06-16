import os
import sys
import pytest
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
    calendar_service = GoogleCalendarService()
    gmail_service = GoogleGmailService()
    tasks_service = GoogleTasksService()
    drive_service = GoogleDriveService()
    sheets_service = GoogleSheetsService()
    maps_service = GoogleMapsService()
    calendar_service.authenticate()
    gmail_service.authenticate()
    tasks_service.authenticate()
    drive_service.authenticate()
    sheets_service.authenticate()
    maps_service.authenticate()
    agent = PersonalTrainerAgent(
        calendar_service=calendar_service,
        gmail_service=gmail_service,
        tasks_service=tasks_service,
        drive_service=drive_service,
        sheets_service=sheets_service,
        maps_service=maps_service
    )
    return agent

@pytest.mark.asyncio
async def test_find_nearby_workout_locations(agent):
    messages = [
        HumanMessage(content="Find me workout locations near 1 Infinite Loop, Cupertino, CA")
    ]
    response = await agent.process_messages(messages)
    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 0
    assert "workout" in response.lower()
    assert "location" in response.lower()

if __name__ == '__main__':
    pytest.main() 