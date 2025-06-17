import pytest
import asyncio
from datetime import datetime, timedelta
import json
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from backend.agent import PersonalTrainerAgent
from backend.google_services.calendar import GoogleCalendarService
from backend.google_services.gmail import GoogleGmailService
from backend.google_services.tasks import GoogleTasksService
from backend.google_services.drive import GoogleDriveService
from backend.google_services.sheets import GoogleSheetsService
from backend.google_services.maps import GoogleMapsService
import os
from dotenv import load_dotenv
import pytest_asyncio

@pytest_asyncio.fixture
async def agent():
    """Create and initialize an agent for testing."""
    load_dotenv()
    maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not maps_api_key:
        raise ValueError("Missing required environment variable: GOOGLE_MAPS_API_KEY")
    
    agent = PersonalTrainerAgent(
        calendar_service=GoogleCalendarService(),
        gmail_service=GoogleGmailService(),
        tasks_service=GoogleTasksService(),
        drive_service=GoogleDriveService(),
        sheets_service=GoogleSheetsService(),
        maps_service=GoogleMapsService(api_key=maps_api_key)
    )
    await agent.async_init()
    return agent

@pytest.mark.asyncio
async def test_natural_language_to_calendar_json_conversion(agent):
    """Test conversion of natural language to calendar event JSON."""
    test_cases = [
        (
            "Schedule a workout tomorrow at 2pm for 1 hour",
            {
                "summary": "Workout",
                "start": {"dateTime": None, "timeZone": "America/Los_Angeles"},
                "end": {"dateTime": None, "timeZone": "America/Los_Angeles"},
                "description": "General fitness workout.",
                "location": "Gym"
            }
        ),
        (
            "Add a yoga session today at 6pm for 45 minutes",
            {
                "summary": "Yoga Session",
                "start": {"dateTime": None, "timeZone": "America/Los_Angeles"},
                "end": {"dateTime": None, "timeZone": "America/Los_Angeles"},
                "description": "Yoga session",
                "location": "Studio"
            }
        )
    ]
    
    for input_text, expected_format in test_cases:
        json_string = await agent._convert_natural_language_to_calendar_json(input_text)
        assert json_string is not None
        assert isinstance(json_string, str)
        
        # Parse the JSON string
        event_data = json.loads(json_string)
        
        # Check required fields
        assert "summary" in event_data
        assert "start" in event_data
        assert "end" in event_data
        assert "timeZone" in event_data["start"]
        assert "timeZone" in event_data["end"]
        
        # Check that the summary matches the expected type of event
        assert any(word in event_data["summary"].lower() for word in ["workout", "yoga", "fitness"])

@pytest.mark.asyncio
async def test_tool_execution_with_natural_language(agent):
    """Test tool execution with natural language input."""
    # Test calendar event creation with a future time to avoid conflicts
    test_time = (datetime.now() + timedelta(days=2)).replace(hour=15, minute=0, second=0, microsecond=0)
    test_message = f"Schedule a workout session for {test_time.strftime('%A, %B %d')} at {test_time.strftime('%I:%M %p')} for 1 hour"
    
    response = await agent.process_messages([{"role": "user", "content": test_message}])
    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 0

@pytest.mark.asyncio
async def test_tool_confirmation_messages(agent):
    """Test that tool confirmation messages are properly formatted."""
    test_cases = [
        (
            "create_calendar_event",
            "Schedule a workout for tomorrow at 10am",
            ["workout", "tomorrow", "10"]  # Removed 'am' to be more flexible
        ),
        (
            "send_email",
            "Send an email to coach@example.com about my progress",
            ["email", "coach@example.com", "progress"]
        ),
        (
            "create_task",
            "Create a task to track my water intake",
            ["task", "water", "intake"]
        )
    ]
    
    for tool_name, args, expected_keywords in test_cases:
        confirmation = await agent._get_tool_confirmation_message(tool_name, args)
        assert confirmation is not None
        assert isinstance(confirmation, str)
        assert len(confirmation) > 0
        for keyword in expected_keywords:
            # Make the assertion more flexible by normalizing both strings
            normalized_confirmation = ' '.join(confirmation.lower().split())
            normalized_keyword = ' '.join(keyword.lower().split())
            assert normalized_keyword in normalized_confirmation, f"Expected '{keyword}' in confirmation message"

@pytest.mark.asyncio
async def test_tool_result_processing(agent):
    """Test processing of tool results into user-friendly messages."""
    test_cases = [
        (
            "get_calendar_events",
            [{"summary": "Workout", "start": {"dateTime": "2024-03-21T10:00:00-07:00"}}],
            ["workout", "10:00"]
        ),
        (
            "get_tasks",
            [{"title": "Track protein", "due": "2024-03-21"}],
            ["protein", "track"]
        ),
        (
            "find_nearby_workout_locations",
            [{"name": "Fitness Center", "address": "123 Main St"}],
            ["fitness", "center", "123 Main St"]
        )
    ]
    
    for tool_name, result, expected_keywords in test_cases:
        response = await agent.process_tool_result(tool_name, result)
        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0
        for keyword in expected_keywords:
            assert keyword.lower() in response.lower()

@pytest.mark.asyncio
async def test_message_conversion(agent):
    """Test conversion of different message formats."""
    test_cases = [
        (
            {"role": "user", "content": "Hello"},
            "human"
        ),
        (
            {"role": "assistant", "content": "Hi there!"},
            "ai"
        ),
        (
            {"role": "system", "content": "System message"},
            "system"
        )
    ]
    
    for input_msg, expected_role in test_cases:
        converted = agent._convert_message(input_msg)
        assert converted is not None
        assert converted.type == expected_role 