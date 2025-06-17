import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from backend.agent import PersonalTrainerAgent
from backend.google_services.calendar import GoogleCalendarService
from backend.google_services.gmail import GoogleGmailService
from backend.google_services.tasks import GoogleTasksService
from backend.google_services.drive import GoogleDriveService
from backend.google_services.sheets import GoogleSheetsService
from backend.google_services.maps import GoogleMapsService
from dotenv import load_dotenv
import os

@pytest_asyncio.fixture
async def agent():
    """Create and initialize an agent for testing."""
    load_dotenv()
    
    # Check for required environment variables
    required_vars = [
        "GOOGLE_MAPS_API_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CALENDAR_ID"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    # Initialize services with proper credentials
    calendar_service = GoogleCalendarService()
    await calendar_service.async_init()  # Ensure calendar service is initialized
    
    agent = PersonalTrainerAgent(
        calendar_service=calendar_service,
        gmail_service=GoogleGmailService(),
        tasks_service=GoogleTasksService(),
        drive_service=GoogleDriveService(),
        sheets_service=GoogleSheetsService(),
        maps_service=GoogleMapsService(api_key=os.getenv("GOOGLE_MAPS_API_KEY"))
    )
    await agent.async_init()
    return agent

@pytest.mark.asyncio
async def test_calendar_conflict_detection(agent):
    """Test that calendar conflicts are properly detected."""
    # Create a test event
    test_time = (datetime.now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    test_event = {
        "summary": "Test Event",
        "start": {
            "dateTime": test_time.isoformat(),
            "timeZone": "America/Los_Angeles"
        },
        "end": {
            "dateTime": (test_time + timedelta(hours=1)).isoformat(),
            "timeZone": "America/Los_Angeles"
        }
    }

    # Create the initial event
    await agent.calendar_service.write_event(test_event)

    # Try to create a conflicting event
    conflicting_event = {
        "summary": "Conflicting Event",
        "start": {
            "dateTime": test_time.isoformat(),
            "timeZone": "America/Los_Angeles"
        },
        "end": {
            "dateTime": (test_time + timedelta(hours=1)).isoformat(),
            "timeZone": "America/Los_Angeles"
        }
    }

    # Check for conflicts
    conflicts = await agent.calendar_service.check_for_conflicts(conflicting_event)
    assert len(conflicts) > 0

@pytest.mark.asyncio
async def test_calendar_conflict_resolution_replace(agent):
    """Test resolving calendar conflicts by replacing the existing event."""
    # Create a test event
    test_time = (datetime.now() + timedelta(days=2)).replace(hour=14, minute=0, second=0, microsecond=0)
    test_event = {
        "summary": "Test Event",
        "start": {
            "dateTime": test_time.isoformat(),
            "timeZone": "America/Los_Angeles"
        },
        "end": {
            "dateTime": (test_time + timedelta(hours=1)).isoformat(),
            "timeZone": "America/Los_Angeles"
        }
    }

    # Create the initial event
    await agent.calendar_service.write_event(test_event)

    # Create a conflicting event and resolve by replacing
    conflicting_event = {
        "summary": "Replacement Event",
        "start": {
            "dateTime": test_time.isoformat(),
            "timeZone": "America/Los_Angeles"
        },
        "end": {
            "dateTime": (test_time + timedelta(hours=1)).isoformat(),
            "timeZone": "America/Los_Angeles"
        }
    }

    # Resolve the conflict
    result = await agent._resolve_calendar_conflict({
        "event_details": conflicting_event,
        "action": "replace"
    })

    assert result is not None
    assert "id" in result

@pytest.mark.asyncio
async def test_calendar_conflict_resolution_skip(agent):
    """Test resolving calendar conflicts by skipping the new event."""
    # Create a test event
    test_time = (datetime.now() + timedelta(days=2)).replace(hour=16, minute=0, second=0, microsecond=0)
    test_event = {
        "summary": "Test Event",
        "start": {
            "dateTime": test_time.isoformat(),
            "timeZone": "America/Los_Angeles"
        },
        "end": {
            "dateTime": (test_time + timedelta(hours=1)).isoformat(),
            "timeZone": "America/Los_Angeles"
        }
    }

    # Create the initial event
    await agent.calendar_service.write_event(test_event)

    # Create a conflicting event and resolve by skipping
    conflicting_event = {
        "summary": "Skipped Event",
        "start": {
            "dateTime": test_time.isoformat(),
            "timeZone": "America/Los_Angeles"
        },
        "end": {
            "dateTime": (test_time + timedelta(hours=1)).isoformat(),
            "timeZone": "America/Los_Angeles"
        }
    }

    # Resolve the conflict
    result = await agent._resolve_calendar_conflict({
        "event_details": conflicting_event,
        "action": "skip"
    })

    assert result is not None
    assert "skipped" in result.lower()

@pytest.mark.asyncio
async def test_calendar_conflict_resolution_invalid_action(agent):
    """Test handling of invalid conflict resolution actions."""
    test_time = (datetime.now() + timedelta(days=2)).replace(hour=18, minute=0, second=0, microsecond=0)
    test_event = {
        "summary": "Test Event",
        "start": {
            "dateTime": test_time.isoformat(),
            "timeZone": "America/Los_Angeles"
        },
        "end": {
            "dateTime": (test_time + timedelta(hours=1)).isoformat(),
            "timeZone": "America/Los_Angeles"
        }
    }

    # Try to resolve with an invalid action
    response = await agent._resolve_calendar_conflict({
        "event_details": test_event,
        "action": "invalid_action"
    })

    assert response is not None
    assert "error" in response.lower() or "invalid" in response.lower() 