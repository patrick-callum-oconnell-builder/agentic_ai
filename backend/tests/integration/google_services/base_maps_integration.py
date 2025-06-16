import os
import sys
import unittest
from dotenv import load_dotenv

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(backend_dir)

from google_services.maps import GoogleMapsService
from google_services.calendar import GoogleCalendarService
from google_services.gmail import GoogleGmailService
from google_services.tasks import GoogleTasksService
from google_services.drive import GoogleDriveService
from google_services.sheets import GoogleSheetsService
from agent import PersonalTrainerAgent

class BaseGoogleMapsIntegrationTest(unittest.TestCase):
    """Base class for Google Maps API integration tests (API key-based)."""
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            raise unittest.SkipTest("Missing required environment variable: GOOGLE_MAPS_API_KEY")
        
        # Initialize services
        cls.calendar_service = GoogleCalendarService()
        cls.gmail_service = GoogleGmailService()
        cls.tasks_service = GoogleTasksService()
        cls.drive_service = GoogleDriveService()
        cls.sheets_service = GoogleSheetsService()
        cls.maps_service = GoogleMapsService()
        
        # Initialize agent with real services
        cls.agent = PersonalTrainerAgent(
            calendar_service=cls.calendar_service,
            gmail_service=cls.gmail_service,
            tasks_service=cls.tasks_service,
            drive_service=cls.drive_service,
            sheets_service=cls.sheets_service,
            maps_service=cls.maps_service
        )

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Ensure services are authenticated
        self.calendar_service.authenticate()
        self.gmail_service.authenticate()
        self.tasks_service.authenticate()
        self.drive_service.authenticate()
        self.sheets_service.authenticate()
        self.maps_service.authenticate() 