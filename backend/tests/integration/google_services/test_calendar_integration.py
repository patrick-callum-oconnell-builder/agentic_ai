import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage
from backend.tests.unit.test_utils import llm_check_response_intent
import asyncio
import pytest

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.integration.google_services.base_google_integration import BaseGoogleIntegrationTest
from backend.agent import PersonalTrainerAgent
from backend.google_services.calendar import GoogleCalendarService
from backend.google_services.gmail import GoogleGmailService
from backend.google_services.tasks import GoogleTasksService
from backend.google_services.drive import GoogleDriveService
from backend.google_services.sheets import GoogleSheetsService
from backend.google_services.maps import GoogleMapsService

@pytest.fixture
async def agent():
    calendar_service = GoogleCalendarService()
    gmail_service = GoogleGmailService()
    tasks_service = GoogleTasksService()
    drive_service = GoogleDriveService()
    sheets_service = GoogleSheetsService()
    maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not maps_api_key:
        raise ValueError("Missing required environment variable: GOOGLE_MAPS_API_KEY")
    maps_service = GoogleMapsService(api_key=maps_api_key)
    
    agent = PersonalTrainerAgent(
        calendar_service=calendar_service,
        gmail_service=gmail_service,
        tasks_service=tasks_service,
        drive_service=drive_service,
        sheets_service=sheets_service,
        maps_service=maps_service
    )
    await agent.async_init()
    return agent

class TestCalendarIntegration(BaseGoogleIntegrationTest):
    """Test suite for Google Calendar integration."""
    
    def test_fetch_upcoming_events(self):
        """Test fetching upcoming events."""
        try:
            # Fetch upcoming events using the agent's calendar service
            events = self.agent.calendar_service.get_upcoming_events()
            self.assertIsInstance(events, list)
            print(f"Calendar test: Successfully fetched {len(events)} upcoming events")
        except Exception as e:
            self.fail(f"Failed to fetch upcoming events: {str(e)}")
            
    def test_schedule_workout(self):
        """Test scheduling a workout."""
        try:
            # Create a test workout event
            workout = {
                "summary": "Upper Body Workout",
                "description": "Focus on chest and shoulders",
                "start": {
                    "dateTime": "2024-03-21T10:00:00Z",
                    "timeZone": "America/Los_Angeles"
                },
                "end": {
                    "dateTime": "2024-03-21T11:00:00Z",
                    "timeZone": "America/Los_Angeles"
                }
            }
            
            # Schedule the workout using the agent's calendar service
            result = self.agent.calendar_service.write_event(workout)
            self.assertIsNotNone(result)
            self.assertIn('id', result)
            print(f"Calendar test: Successfully scheduled workout")
        except Exception as e:
            self.fail(f"Failed to schedule workout: {str(e)}")

    async def test_tool_confirmation_and_response(self):
        """Test that a tool call yields both a confirmation and a tool result message."""
        # Compose a user message that will trigger a calendar tool call
        user_message = HumanMessage(content="Add a workout to my calendar for tomorrow at 10am called 'Test Workout'.")
        # Call the agent's process_messages method and await the response
        responses = await self.agent.process_messages([user_message])
        # The agent should return a string or a list of messages; handle both
        if isinstance(responses, str):
            # If a string, treat as a single message
            messages = [responses]
        elif isinstance(responses, list):
            messages = responses
        else:
            self.fail(f"Unexpected response type: {type(responses)}")
        # There should be at least two messages: confirmation and tool result
        self.assertGreaterEqual(len(messages), 2, f"Expected at least 2 messages, got {len(messages)}: {messages}")
        # Use the LLM to check the intent of each message
        confirmation_intent = "Confirm to the user that a calendar event was added as requested."
        tool_result_intent = "Provide the user with the result or details of the calendar event that was added."
        confirmation_ok = llm_check_response_intent(messages[0], confirmation_intent)
        tool_result_ok = llm_check_response_intent(messages[1], tool_result_intent)
        self.assertTrue(confirmation_ok, f"First message did not confirm the tool action as expected: {messages[0]}")
        self.assertTrue(tool_result_ok, f"Second message did not provide the tool result as expected: {messages[1]}")

@pytest.mark.asyncio
async def test_calendar_query_returns_friendly_response(agent):
    agent_instance = await agent
    messages = [{"role": "user", "content": "Show me my workouts this week"}]
    response = await agent_instance.process_messages(messages)
    print(f"\nActual response: {response}\n")  # Debug logging
    assert response is not None
    assert isinstance(response, str)
    assert "tool=" not in response
    assert "message_log" not in response
    assert "AIMessage" not in response

if __name__ == '__main__':
    unittest.main() 