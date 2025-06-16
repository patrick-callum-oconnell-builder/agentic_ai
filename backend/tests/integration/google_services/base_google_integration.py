import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(backend_dir)

from agent import PersonalTrainerAgent
from google_services.calendar import GoogleCalendarService
from google_services.gmail import GoogleGmailService
from google_services.fit import GoogleFitnessService
from google_services.tasks import GoogleTasksService
from google_services.drive import GoogleDriveService
from google_services.sheets import GoogleSheetsService
from google_services.maps import GoogleMapsService
from google_services.auth import get_google_credentials

class BaseGoogleIntegrationTest(unittest.TestCase):
    """Base class for Google API integration tests."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before running tests."""
        # Load environment variables
        load_dotenv()
        
        # Check for required environment variables
        required_vars = [
            'GOOGLE_CLIENT_ID',
            'GOOGLE_CLIENT_SECRET'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise unittest.SkipTest(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Initialize services without passing credentials
        cls.calendar_service = GoogleCalendarService()
        cls.drive_service = GoogleDriveService()
        cls.fit_service = GoogleFitnessService()
        cls.gmail_service = GoogleGmailService()
        cls.sheets_service = GoogleSheetsService()
        cls.tasks_service = GoogleTasksService()
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
        self.fit_service.authenticate()
        self.tasks_service.authenticate()
        self.drive_service.authenticate()
        self.sheets_service.authenticate() 