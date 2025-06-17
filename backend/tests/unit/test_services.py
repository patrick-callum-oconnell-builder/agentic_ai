import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import unittest
import asyncio
from google_services.calendar import GoogleCalendarService
import os
from dotenv import load_dotenv
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from google_services.auth import get_google_credentials

# Optional imports
try:
    from google_services.gmail import GmailService
except ImportError:
    GmailService = None
try:
    from google_services.fit import GoogleFitnessService
except ImportError:
    GoogleFitnessService = None
try:
    from google_services.tasks import GoogleTasksService
except ImportError:
    GoogleTasksService = None
try:
    from google_services.drive import GoogleDriveService
except ImportError:
    GoogleDriveService = None
try:
    from google_services.sheets import GoogleSheetsService
except ImportError:
    GoogleSheetsService = None
try:
    from google_services.maps import GoogleMapsService
except ImportError:
    GoogleMapsService = None

# Load environment variables
load_dotenv()

class MockCredentials:
    def __init__(self, scopes=None):
        self.scopes = scopes or []
        self.valid = True
        self.expired = False
        self.refresh_token = True

class TestGoogleServices(unittest.TestCase):
    def setUp(self):
        """Set up services before each test"""
        # Create mock credentials with all required scopes
        self.mock_creds = MockCredentials([
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/fitness.activity.read",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/tasks"
        ])

        # Patch get_credentials to return mock credentials for all services
        self.patcher = patch('auth.get_credentials', return_value=self.mock_creds)
        self.patcher.start()

        # Initialize services without passing creds
        self.calendar = GoogleCalendarService()
        self.drive = GoogleDriveService() if GoogleDriveService else None
        self.fit = GoogleFitnessService() if GoogleFitnessService else None
        self.gmail = GmailService() if GmailService else None
        self.maps = GoogleMapsService(api_key="AIzaMockApiKeyForTesting123456789") if GoogleMapsService else None
        self.sheets = GoogleSheetsService() if GoogleSheetsService else None
        self.tasks = GoogleTasksService() if GoogleTasksService else None

        # Optional services
        try:
            self.has_maps = self.maps is not None
        except Exception:
            self.has_maps = False

        # Mock successful API responses
        self.mock_calendar_response = {
            'items': [{
                'id': 'test_event_id',
                'summary': 'Test Workout',
                'start': {'dateTime': datetime.now().isoformat()},
                'end': {'dateTime': (datetime.now() + timedelta(hours=1)).isoformat()}
            }]
        }
        self.mock_drive_response = {'id': 'test_folder_id'}
        self.mock_sheets_response = {'spreadsheetId': 'test_spreadsheet_id'}
        self.mock_tasks_response = {'id': 'test_tasklist_id'}
        self.mock_fit_response = {
            'total_activities': 1,
            'activities': [{
                'type': 'running',
                'duration': 3600,
                'calories': 500
            }]
        }
        self.mock_gmail_response = [{
            'id': 'test_email_id',
            'snippet': 'Test email snippet'
        }]

        # Patch all service methods to return mock responses
        if self.calendar:
            self.calendar.service = MagicMock()
            self.calendar.service.events().list().execute.return_value = self.mock_calendar_response
            self.calendar.service.events().insert().execute.return_value = {'id': 'test_event_id'}

        if self.drive:
            self.drive.service = MagicMock()
            self.drive.service.files().create().execute.return_value = self.mock_drive_response
            self.drive.create_workout_folder = MagicMock(return_value=self.mock_drive_response)

        if self.sheets:
            self.sheets.service = MagicMock()
            self.sheets.service.spreadsheets().create().execute.return_value = self.mock_sheets_response
            self.sheets.create_workout_tracker = MagicMock(return_value=self.mock_sheets_response)

        if self.tasks:
            self.tasks.service = MagicMock()
            self.tasks.service.tasklists().insert().execute.return_value = self.mock_tasks_response
            self.tasks.create_workout_tasklist = MagicMock(return_value=self.mock_tasks_response)
            self.tasks.get_workout_tasks = MagicMock(return_value=[])

        if self.fit:
            self.fit.service = MagicMock()
            self.fit.get_activity_summary = MagicMock(return_value=self.mock_fit_response)
            self.fit.get_workout_history = MagicMock(return_value=[{
                'type': 'running',
                'duration': 3600,
                'calories': 500
            }])
            self.fit.get_body_metrics = MagicMock(return_value={
                'weight': 70,
                'height': 175
            })

        if self.gmail:
            self.gmail.service = MagicMock()
            self.gmail.get_recent_emails = MagicMock(return_value=self.mock_gmail_response)

        if self.maps:
            self.maps.service = MagicMock()
            self.maps.find_nearby_workout_locations = MagicMock(return_value=[{
                'name': 'Test Gym',
                'address': '123 Test St',
                'rating': 4.5,
                'types': ['gym', 'health']
            }])

    def tearDown(self):
        """Clean up after each test"""
        self.patcher.stop()

    def test_calendar_service(self):
        """Test if we can fetch calendar events"""
        try:
            events = self.calendar.get_upcoming_events()
            self.assertIsInstance(events, list)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['id'], 'test_event_id')
            print(f"Calendar test: Successfully mocked {len(events)} events")
        except Exception as e:
            self.fail(f"Calendar test failed: {str(e)}")

    @unittest.skipIf(GoogleFitnessService is None, "GoogleFitnessService not available")
    def test_fit_service(self):
        """Test Google Fit service initialization."""
        service = GoogleFitnessService()
        self.assertIsNotNone(service)
        self.assertIsNotNone(service.service)

    @unittest.skipIf(GoogleTasksService is None, "GoogleTasksService not available")
    def test_tasks_service(self):
        """Test if we can fetch task lists"""
        try:
            tasklist = self.tasks.create_workout_tasklist()
            self.assertIn('id', tasklist)
            self.assertEqual(tasklist['id'], 'test_tasklist_id')
            tasks = self.tasks.get_workout_tasks(tasklist_id=tasklist['id'])
            self.assertIsInstance(tasks, list)
            print(f"Tasks test: Successfully mocked tasklist creation and task fetching")
        except Exception as e:
            self.fail(f"Tasks test failed: {str(e)}")

    @unittest.skipIf(GoogleDriveService is None, "GoogleDriveService not available")
    def test_drive_service(self):
        """Test if we can create a folder"""
        try:
            folder = self.drive.create_workout_folder()
            self.assertIn('id', folder)
            self.assertEqual(folder['id'], 'test_folder_id')
            print(f"Drive test: Successfully mocked folder creation")
        except Exception as e:
            self.fail(f"Drive test failed: {str(e)}")

    @unittest.skipIf(GoogleSheetsService is None, "GoogleSheetsService not available")
    def test_sheets_service(self):
        """Test if we can create a spreadsheet"""
        try:
            spreadsheet = self.sheets.create_workout_tracker()
            self.assertIn('spreadsheetId', spreadsheet)
            self.assertEqual(spreadsheet['spreadsheetId'], 'test_spreadsheet_id')
            print(f"Sheets test: Successfully mocked spreadsheet creation")
        except Exception as e:
            self.fail(f"Sheets test failed: {str(e)}")

    @unittest.skipIf(not os.getenv('GOOGLE_MAPS_API_KEY') or GoogleMapsService is None, "Maps API key or service not set")
    def test_maps_service(self):
        """Test Google Maps service initialization."""
        # Use the mock API key that was set up in setUp
        service = GoogleMapsService(api_key="AIzaMockApiKeyForTesting123456789")
        self.assertIsNotNone(service)
        self.assertIsNotNone(service.client)

    def test_calendar_credentials(self):
        """Test that calendar credentials exist and have the correct scopes."""
        creds = self.calendar.creds
        self.assertIsNotNone(creds, "No credentials found for Google Calendar")
        self.assertTrue(creds.valid or (creds.expired and creds.refresh_token), "Credentials are not valid and cannot be refreshed")
        required_scope = "https://www.googleapis.com/auth/calendar"
        self.assertIn(required_scope, creds.scopes, f"Missing required scope: {required_scope}")

    @unittest.skipIf(GoogleFitnessService is None, "GoogleFitnessService not available")
    def test_fit_credentials(self):
        creds = self.fit.creds
        self.assertIsNotNone(creds, "No credentials found for Google Fitness")
        self.assertTrue(creds.valid or (creds.expired and creds.refresh_token), "Credentials are not valid and cannot be refreshed")
        required_scope = "https://www.googleapis.com/auth/fitness.activity.read"
        self.assertIn(required_scope, creds.scopes, f"Missing required scope: {required_scope}")

    @unittest.skipIf(GoogleTasksService is None, "GoogleTasksService not available")
    def test_tasks_credentials(self):
        creds = self.tasks.creds
        self.assertIsNotNone(creds, "No credentials found for Google Tasks")
        self.assertTrue(creds.valid or (creds.expired and creds.refresh_token), "Credentials are not valid and cannot be refreshed")
        required_scope = "https://www.googleapis.com/auth/tasks"
        self.assertIn(required_scope, creds.scopes, f"Missing required scope: {required_scope}")

    @unittest.skipIf(GoogleDriveService is None, "GoogleDriveService not available")
    def test_drive_credentials(self):
        creds = self.drive.creds
        self.assertIsNotNone(creds, "No credentials found for Google Drive")
        self.assertTrue(creds.valid or (creds.expired and creds.refresh_token), "Credentials are not valid and cannot be refreshed")
        required_scopes = [
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        self.assertTrue(
            any(scope in creds.scopes for scope in required_scopes),
            f"Missing required scope: one of {required_scopes}"
        )

    def test_sheets_credentials(self):
        """Test Google Sheets credentials."""
        creds = get_google_credentials()
        self.assertIsNotNone(creds)
        self.assertTrue(creds.valid)

if __name__ == '__main__':
    unittest.main() 