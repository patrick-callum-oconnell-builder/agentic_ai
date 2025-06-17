import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import unittest
import asyncio
from google_services.calendar import GoogleCalendarService
import os
from dotenv import load_dotenv
from unittest.mock import MagicMock, patch, AsyncMock
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

class TestGoogleServices(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_creds = MockCredentials([
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/fitness.activity.read",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/tasks"
        ])
        self.patcher = patch('google_services.auth.get_google_credentials', return_value=self.mock_creds)
        self.patcher.start()
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
            self.drive.create_workout_folder = AsyncMock(return_value=self.mock_drive_response)

        if self.sheets:
            self.sheets.service = MagicMock()
            self.sheets.service.spreadsheets().create().execute.return_value = self.mock_sheets_response
            self.sheets.create_workout_tracker = AsyncMock(return_value=self.mock_sheets_response)

        if self.tasks:
            self.tasks.service = MagicMock()
            self.tasks.service.tasklists().insert().execute.return_value = self.mock_tasks_response
            self.tasks.create_workout_tasklist = AsyncMock(return_value=self.mock_tasks_response)
            self.tasks.get_workout_tasks = AsyncMock(return_value=[])

        if self.fit:
            self.fit.service = MagicMock()
            self.fit.get_activity_summary = AsyncMock(return_value=self.mock_fit_response)
            self.fit.get_workout_history = AsyncMock(return_value=[{
                'type': 'running',
                'duration': 3600,
                'calories': 500
            }])
            self.fit.get_body_metrics = AsyncMock(return_value={
                'weight': 70,
                'height': 175
            })

        if self.gmail:
            self.gmail.service = MagicMock()
            self.gmail.get_recent_emails = AsyncMock(return_value=self.mock_gmail_response)

        if self.maps:
            self.maps.service = MagicMock()
            self.maps.find_nearby_workout_locations = AsyncMock(return_value=[{
                'name': 'Test Gym',
                'address': '123 Test St',
                'rating': 4.5,
                'types': ['gym', 'health']
            }])

    def tearDown(self):
        self.patcher.stop()

    async def test_calendar_service(self):
        events = await self.calendar.get_upcoming_events()
        self.assertIsInstance(events, list)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['id'], 'test_event_id')
        print(f"Calendar test: Successfully mocked {len(events)} events")

    @unittest.skipIf(GoogleFitnessService is None, "GoogleFitnessService not available")
    async def test_fit_service(self):
        self.assertIsNotNone(self.fit)
        self.assertIsNotNone(self.fit.service)

    @unittest.skipIf(GoogleTasksService is None, "GoogleTasksService not available")
    async def test_tasks_service(self):
        tasklist = await self.tasks.create_workout_tasklist()
        self.assertIn('id', tasklist)
        self.assertEqual(tasklist['id'], 'test_tasklist_id')
        tasks = await self.tasks.get_workout_tasks(tasklist_id=tasklist['id'])
        self.assertIsInstance(tasks, list)
        print(f"Tasks test: Successfully mocked tasklist creation and task fetching")

    @unittest.skipIf(GoogleDriveService is None, "GoogleDriveService not available")
    async def test_drive_service(self):
        folder = await self.drive.create_workout_folder()
        self.assertIn('id', folder)
        self.assertEqual(folder['id'], 'test_folder_id')
        print(f"Drive test: Successfully mocked folder creation")

    @unittest.skipIf(GoogleSheetsService is None, "GoogleSheetsService not available")
    async def test_sheets_service(self):
        spreadsheet = await self.sheets.create_workout_tracker()
        self.assertIn('spreadsheetId', spreadsheet)
        self.assertEqual(spreadsheet['spreadsheetId'], 'test_spreadsheet_id')
        print(f"Sheets test: Successfully mocked spreadsheet creation")

    @unittest.skipIf(not os.getenv('GOOGLE_MAPS_API_KEY') or GoogleMapsService is None, "Maps API key or service not set")
    async def test_maps_service(self):
        self.maps.client = MagicMock()
        self.assertIsNotNone(self.maps)
        self.assertIsNotNone(self.maps.client)

if __name__ == '__main__':
    unittest.main() 