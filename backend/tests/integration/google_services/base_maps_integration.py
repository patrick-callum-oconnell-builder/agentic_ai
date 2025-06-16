import os
import sys
import pytest
import asyncio
import logging
from dotenv import load_dotenv

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(backend_dir)

from backend.google_services.maps import GoogleMapsService
from backend.google_services.calendar import GoogleCalendarService
from backend.google_services.gmail import GoogleGmailService
from backend.google_services.tasks import GoogleTasksService
from backend.google_services.drive import GoogleDriveService
from backend.google_services.sheets import GoogleSheetsService
from backend.agent import PersonalTrainerAgent

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class BaseMapsIntegrationTest:
    @pytest.fixture(autouse=True)
    async def setup(self):
        load_dotenv()
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            pytest.skip("Missing required environment variable: GOOGLE_MAPS_API_KEY")

        # Initialize services
        self.calendar_service = GoogleCalendarService()
        self.gmail_service = GoogleGmailService()
        self.tasks_service = GoogleTasksService()
        self.drive_service = GoogleDriveService()
        self.sheets_service = GoogleSheetsService()
        self.maps_service = GoogleMapsService()

        # Authenticate all services
        self.calendar_service.authenticate()
        self.gmail_service.authenticate()
        self.tasks_service.authenticate()
        self.drive_service.authenticate()
        self.sheets_service.authenticate()
        # self.maps_service.authenticate()  # Removed as GoogleMapsService does not have authenticate

        # Initialize agent with real services asynchronously
        self.agent = await PersonalTrainerAgent.ainit(
            calendar_service=self.calendar_service,
            gmail_service=self.gmail_service,
            tasks_service=self.tasks_service,
            drive_service=self.drive_service,
            sheets_service=self.sheets_service,
            maps_service=self.maps_service
        )
        # No yield here, just return 