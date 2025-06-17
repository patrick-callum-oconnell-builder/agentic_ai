import os
import sys
import pytest
from dotenv import load_dotenv
import asyncio

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(backend_dir)

from agent import PersonalTrainerAgent
from google_services.calendar import GoogleCalendarService
from google_services.gmail import GoogleGmailService
from google_services.fit import GoogleFitnessService
from google_services.tasks import GoogleTasksService
from google_services.drive import GoogleDriveService
from google_services.sheets import GoogleSheetsService
from google_services.maps import GoogleMapsService

@pytest.fixture(scope="function")
async def google_services():
    """Set up Google services for testing."""
    load_dotenv()
    required_vars = [
        'GOOGLE_CLIENT_ID',
        'GOOGLE_CLIENT_SECRET'
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        pytest.skip(f"Missing required environment variables: {', '.join(missing_vars)}")
    calendar_service = GoogleCalendarService()
    drive_service = GoogleDriveService()
    fit_service = GoogleFitnessService()
    gmail_service = GoogleGmailService()
    sheets_service = GoogleSheetsService()
    tasks_service = GoogleTasksService()
    maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not maps_api_key:
        raise ValueError("Missing required environment variable: GOOGLE_MAPS_API_KEY")
    maps_service = GoogleMapsService(api_key=maps_api_key)
    await calendar_service.authenticate()
    await gmail_service.authenticate()
    await fit_service.authenticate()
    await tasks_service.authenticate()
    await drive_service.authenticate()
    await sheets_service.authenticate()
    maps_service.authenticate()  # Maps service doesn't need async auth
    return {
        'calendar_service': calendar_service,
        'drive_service': drive_service,
        'fit_service': fit_service,
        'gmail_service': gmail_service,
        'sheets_service': sheets_service,
        'tasks_service': tasks_service,
        'maps_service': maps_service
    }

@pytest.fixture(scope="function")
async def agent(google_services):
    services = await google_services
    agent = PersonalTrainerAgent(
        calendar_service=services['calendar_service'],
        gmail_service=services['gmail_service'],
        tasks_service=services['tasks_service'],
        drive_service=services['drive_service'],
        sheets_service=services['sheets_service'],
        maps_service=services['maps_service']
    )
    await agent.async_init()
    return agent 