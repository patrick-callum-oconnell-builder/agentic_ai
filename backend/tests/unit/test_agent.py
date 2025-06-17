import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from typing import Dict, Any
import os
import sys
import json
import asyncio

from backend.agent import PersonalTrainerAgent
from backend.google_services.calendar import GoogleCalendarService
from backend.google_services.gmail import GoogleGmailService
from backend.google_services.fit import GoogleFitnessService
from backend.google_services.tasks import GoogleTasksService
from backend.google_services.drive import GoogleDriveService
from backend.google_services.sheets import GoogleSheetsService
from backend.google_services.maps import GoogleMapsService

class TestPersonalTrainerAgent(unittest.IsolatedAsyncioTestCase):
    """Test suite for PersonalTrainerAgent class."""

    async def asyncSetUp(self):
        # Create mock services with all required methods
        self.mock_calendar = MagicMock(spec=GoogleCalendarService)
        self.mock_gmail = MagicMock(spec=GoogleGmailService)
        self.mock_fit = MagicMock(spec=GoogleFitnessService)
        self.mock_tasks = MagicMock(spec=GoogleTasksService)
        self.mock_drive = MagicMock(spec=GoogleDriveService)
        self.mock_sheets = MagicMock(spec=GoogleSheetsService)
        self.mock_maps = MagicMock(spec=GoogleMapsService)

        # Set up mock responses for calendar service (async)
        self.mock_calendar.get_upcoming_events = AsyncMock(return_value=[])
        self.mock_calendar.get_events_for_date = AsyncMock(return_value=[])
        self.mock_calendar.write_event = AsyncMock(return_value={"id": "test_event_id"})
        
        # Set up mock responses for Gmail service (async)
        self.mock_gmail.get_recent_emails = AsyncMock(return_value=[])
        
        # Set up mock responses for Fitness service (async)
        self.mock_fit.get_activity_summary = AsyncMock(return_value={"total_activities": 0})
        self.mock_fit.get_workout_history = AsyncMock(return_value=[])
        self.mock_fit.get_body_metrics = AsyncMock(return_value={})
        
        # Set up mock responses for Tasks service (async)
        self.mock_tasks.create_workout_tasklist = AsyncMock(return_value={"id": "test_tasklist_id"})
        self.mock_tasks.add_workout_task = AsyncMock(return_value={"id": "test_task_id"})
        self.mock_tasks.get_workout_tasks = AsyncMock(return_value=[])
        
        # Set up mock responses for Drive service (async)
        self.mock_drive.create_folder = AsyncMock(return_value={"id": "test_folder_id"})
        self.mock_drive.upload_file = AsyncMock(return_value={"id": "test_file_id"})
        
        # Set up mock responses for Sheets service (async)
        self.mock_sheets.create_workout_tracker = AsyncMock(return_value={"id": "test_spreadsheet_id"})
        self.mock_sheets.add_workout_entry = AsyncMock(return_value={"updated": True})
        self.mock_sheets.add_nutrition_entry = AsyncMock(return_value={"updated": True})
        
        # Set up mock responses for Maps service (async)
        self.mock_maps.find_nearby_workout_locations = AsyncMock(return_value=[])

        # Create agent with mock services using the new flexible initialization
        self.agent = PersonalTrainerAgent(
            calendar_service=self.mock_calendar,
            gmail_service=self.mock_gmail,
            tasks_service=self.mock_tasks,
            drive_service=self.mock_drive,
            sheets_service=self.mock_sheets,
            maps_service=self.mock_maps
        )
        await self.agent.async_init()

    def test_initialization(self):
        """Test that the agent initializes correctly with all services."""
        self.assertIsNotNone(self.agent)
        self.assertIsNotNone(self.agent.calendar_service)
        self.assertIsNotNone(self.agent.gmail_service)
        self.assertIsNotNone(self.agent.tasks_service)
        self.assertIsNotNone(self.agent.drive_service)
        self.assertIsNotNone(self.agent.sheets_service)
        self.assertIsNotNone(self.agent.tools)
        # Note: agent attribute is only set after async_init() is called

    def test_tool_creation(self):
        """Test that all tools are created correctly."""
        tools = self.agent.tools
        tool_names = [tool.name for tool in tools]
        
        # Check for the actual tools we're using
        expected_tools = [
            "get_calendar_events",
            "create_calendar_event", 
            "send_email",
            "create_task",
            "get_tasks",
            "search_drive",
            "get_sheet_data"
        ]
        
        # Add maps tools if maps_service is provided
        if self.agent.maps_service:
            expected_tools.extend([
                "get_directions",
                "find_nearby_workout_locations"
            ])
        
        for tool_name in expected_tools:
            self.assertIn(tool_name, tool_names, f"Missing tool: {tool_name}")

    async def test_calendar_tools(self):
        """Test calendar-related tool functionality."""
        await self.agent.calendar_service.get_upcoming_events()
        self.mock_calendar.get_upcoming_events.assert_awaited_once()

        await self.agent.calendar_service.get_events_for_date("today")
        self.mock_calendar.get_events_for_date.assert_awaited_once_with("today")

        event_data = {
            "summary": "Test Workout",
            "start_time": "tomorrow 10am",
            "end_time": "tomorrow 11am",
            "description": "Test workout session",
            "location": "Test Gym"
        }
        await self.agent.calendar_service.write_event(json.dumps(event_data))
        self.mock_calendar.write_event.assert_awaited_once()

    async def test_tasks_tools(self):
        """Test tasks-related tool functionality."""
        await self.agent.tasks_service.create_workout_tasklist()
        self.mock_tasks.create_workout_tasklist.assert_awaited_once()

        await self.agent.tasks_service.add_workout_task(
            tasklist_id="test_tasklist_id",
            workout_name="Test Workout",
            notes="Test notes",
            due_date=datetime.now() + timedelta(days=1)
        )
        self.mock_tasks.add_workout_task.assert_awaited_once()

        await self.agent.tasks_service.get_workout_tasks("test_tasklist_id")
        self.mock_tasks.get_workout_tasks.assert_awaited_once()

    async def test_drive_tools(self):
        """Test drive-related tool functionality."""
        await self.agent.drive_service.create_folder("Test Folder")
        self.mock_drive.create_folder.assert_awaited_once()

        await self.agent.drive_service.upload_file("/path/to/file.txt")
        self.mock_drive.upload_file.assert_awaited_once()

    async def test_sheets_tools(self):
        """Test sheets-related tool functionality."""
        await self.agent.sheets_service.create_workout_tracker()
        self.mock_sheets.create_workout_tracker.assert_awaited_once()

        await self.agent.sheets_service.add_workout_entry()
        self.mock_sheets.add_workout_entry.assert_awaited_once()

        await self.agent.sheets_service.add_nutrition_entry()
        self.mock_sheets.add_nutrition_entry.assert_awaited_once()

    async def test_gmail_tools(self):
        """Test Gmail-related tool functionality."""
        await self.agent.gmail_service.get_recent_emails()
        self.mock_gmail.get_recent_emails.assert_awaited_once()

    @patch('backend.agent.ChatOpenAI')
    async def test_process_messages(self, mock_chat):
        """Test message processing functionality."""
        mock_chat.return_value.invoke.return_value = "I'll help you start working out"
        messages = [
            {"role": "user", "content": "I want to start working out"}
        ]
        result = await self.agent.process_messages(messages)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

if __name__ == '__main__':
    unittest.main() 