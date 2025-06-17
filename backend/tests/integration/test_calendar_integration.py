import pytest
from backend.agent import PersonalTrainerAgent
from backend.google_services.calendar import GoogleCalendarService
from unittest.mock import AsyncMock
from datetime import datetime, timedelta, timezone
import json
import pytz
import asyncio
import re

@pytest.mark.asyncio
async def test_create_calendar_event_natural_language(monkeypatch):
    # Mock the LLM to return valid JSON
    class DummyLLM:
        async def ainvoke(self, messages):
            class Response:
                content = '{"summary": "Workout", "start": {"dateTime": "2024-03-20T10:00:00-07:00", "timeZone": "America/Los_Angeles"}, "end": {"dateTime": "2024-03-20T11:00:00-07:00", "timeZone": "America/Los_Angeles"}}'
            return Response()
    
    agent = PersonalTrainerAgent(
        calendar_service=AsyncMock(spec=GoogleCalendarService),
        gmail_service=None,
        tasks_service=None,
        drive_service=None,
        sheets_service=None,
        maps_service=None
    )
    agent.llm = DummyLLM()
    agent.tools = [t for t in agent.tools if t.name == "create_calendar_event"]
    agent.tools[0].func = AsyncMock(return_value={"id": "123", "summary": "Workout", "start": {"dateTime": "2024-03-20T10:00:00-07:00", "timeZone": "America/Los_Angeles"}, "end": {"dateTime": "2024-03-20T11:00:00-07:00", "timeZone": "America/Los_Angeles"}})
    result = await agent._execute_tool("create_calendar_event", "Workout at 10 AM tomorrow")
    assert result["summary"] == "Workout"
    assert result["start"]["dateTime"] == "2024-03-20T10:00:00-07:00"

@pytest.mark.asyncio
async def test_create_calendar_event_invalid_llm(monkeypatch):
    # Mock the LLM to return invalid (non-JSON) output
    class DummyLLM:
        async def ainvoke(self, messages):
            class Response:
                content = 'Workout at 10 AM tomorrow'
            return Response()
    agent = PersonalTrainerAgent(
        calendar_service=AsyncMock(spec=GoogleCalendarService),
        gmail_service=None,
        tasks_service=None,
        drive_service=None,
        sheets_service=None,
        maps_service=None
    )
    agent.llm = DummyLLM()
    agent.tools = [t for t in agent.tools if t.name == "create_calendar_event"]
    agent.tools[0].func = AsyncMock()
    with pytest.raises(ValueError) as excinfo:
        await agent._execute_tool("create_calendar_event", "Workout at 10 AM tomorrow")
    assert "LLM output" in str(excinfo.value)

@pytest.mark.asyncio
async def test_calendar_timeframe_handling(monkeypatch):
    """Test that calendar event queries properly handle time frames."""
    # Mock the LLM for natural language processing
    class DummyLLM:
        async def ainvoke(self, messages):
            class Response:
                def __init__(self, content):
                    self.content = content
            # Return different responses based on the input
            if "create a workout" in str(messages):
                return Response('{"summary": "Workout", "start": {"dateTime": "2024-03-20T10:00:00-07:00", "timeZone": "America/Los_Angeles"}, "end": {"dateTime": "2024-03-20T11:00:00-07:00", "timeZone": "America/Los_Angeles"}}')
            elif "create another workout" in str(messages):
                return Response('{"summary": "Future Workout", "start": {"dateTime": "2024-03-27T10:00:00-07:00", "timeZone": "America/Los_Angeles"}, "end": {"dateTime": "2024-03-27T11:00:00-07:00", "timeZone": "America/Los_Angeles"}}')
            else:
                return Response("TOOL_CALL: get_calendar_events this week")

    # Create a mock calendar service that tracks events
    class MockCalendarService:
        def __init__(self):
            self.events = []
            self.mock_service = AsyncMock()

        async def write_event(self, event_details):
            self.events.append(event_details)
            return {"id": f"event_{len(self.events)}", **event_details}

        async def get_upcoming_events(self, args=None, max_results=10):
            now = datetime.now(timezone.utc)
            
            # Extract time range from args
            if isinstance(args, dict):
                time_min = datetime.fromisoformat(args.get('timeMin', now.isoformat()))
                time_max = datetime.fromisoformat(args.get('timeMax', (now + timedelta(days=365)).isoformat()))
            else:
                time_min = now
                time_max = now + timedelta(days=365)

            # Filter events within the time range
            filtered_events = []
            for event in self.events:
                start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                if time_min <= start_time <= time_max:
                    filtered_events.append(event)

            return filtered_events

        async def delete_events_in_range(self, time_range):
            """Mock implementation of delete_events_in_range."""
            if isinstance(time_range, dict):
                time_min = datetime.fromisoformat(time_range.get('start_time', ''))
                time_max = datetime.fromisoformat(time_range.get('end_time', ''))
            else:
                # For simplicity in the test, we'll just delete all events
                self.events = []
                return len(self.events)

            # Filter and delete events within the range
            events_to_keep = []
            for event in self.events:
                start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                if not (time_min <= start_time <= time_max):
                    events_to_keep.append(event)

            deleted_count = len(self.events) - len(events_to_keep)
            self.events = events_to_keep
            return deleted_count

        async def get_events_for_date(self, date):
            """Mock implementation of get_events_for_date."""
            target_date = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            return [event for event in self.events if 
                    datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00')).date() == target_date.date()]

    # Create the agent with our mock services
    calendar_service = MockCalendarService()
    agent = PersonalTrainerAgent(
        calendar_service=calendar_service,
        gmail_service=None,
        tasks_service=None,
        drive_service=None,
        sheets_service=None,
        maps_service=None
    )
    agent.llm = DummyLLM()

    # Create two events: one in 3 days, one in 2 weeks
    now = datetime.now(timezone.utc)
    event1_time = (now + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0)
    event2_time = (now + timedelta(days=14)).replace(hour=10, minute=0, second=0, microsecond=0)

    # Create first event
    await agent._execute_tool("create_calendar_event", json.dumps({
        "summary": "Near Workout",
        "start": {"dateTime": event1_time.isoformat(), "timeZone": "America/Los_Angeles"},
        "end": {"dateTime": (event1_time + timedelta(hours=1)).isoformat(), "timeZone": "America/Los_Angeles"}
    }))

    # Create second event
    await agent._execute_tool("create_calendar_event", json.dumps({
        "summary": "Far Workout",
        "start": {"dateTime": event2_time.isoformat(), "timeZone": "America/Los_Angeles"},
        "end": {"dateTime": (event2_time + timedelta(hours=1)).isoformat(), "timeZone": "America/Los_Angeles"}
    }))

    # Query for events in the next week
    result = await agent._execute_tool("get_calendar_events", "this week")
    
    # Verify the results
    assert len(result) == 1, "Should only return one event (the one within the next week)"
    assert result[0]["summary"] == "Near Workout", "Should return the event within the next week"
    assert "Far Workout" not in [event["summary"] for event in result], "Should not return the event from 2 weeks away"

    # Verify the time frame was properly extracted and applied
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    event_time = datetime.fromisoformat(result[0]["start"]["dateTime"].replace('Z', '+00:00'))
    assert start_of_week <= event_time <= end_of_week, "Event should be within the current week"

@pytest.mark.asyncio
async def test_calendar_timeframe_integration():
    """Integration test: add two events, query for next week, verify only correct event is returned."""
    # Setup real services
    calendar_service = GoogleCalendarService()
    agent = PersonalTrainerAgent(
        calendar_service=calendar_service,
        gmail_service=None,
        tasks_service=None,
        drive_service=None,
        sheets_service=None,
        maps_service=None
    )

    # Helper to create event
    async def create_event(summary, start_dt, end_dt):
        event_details = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/Los_Angeles"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/Los_Angeles"},
        }
        return await calendar_service.write_event(event_details)

    # Helper to delete event
    async def delete_event(event_id):
        try:
            await calendar_service.delete_event(event_id)
        except Exception:
            pass

    # Times
    pacific = pytz.timezone('America/Los_Angeles')
    now = datetime.now(pacific)
    event1_start = (now + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0)
    event1_end = event1_start + timedelta(hours=1)
    event2_start = (now + timedelta(days=14)).replace(hour=10, minute=0, second=0, microsecond=0)
    event2_end = event2_start + timedelta(hours=1)

    # Create events
    event1 = await create_event("IntegrationTest-Near", event1_start, event1_end)
    event2 = await create_event("IntegrationTest-Far", event2_start, event2_end)

    try:
        # Query for events in the next week
        user_query = "What events do I have coming up in the next week?"
        # Simulate the agent's full workflow: confirmation, tool call, summary
        confirmation = await agent._format_confirmation("get_calendar_events", user_query)
        assert "next week" in confirmation.lower() or "coming up" in confirmation.lower()
        tool_result = await agent._execute_tool("get_calendar_events", "next week")
        summary = await agent._format_tool_response("get_calendar_events", tool_result)

        # Check that only the near event is present
        assert "IntegrationTest-Near" in summary
        assert "IntegrationTest-Far" not in summary
        # Optionally, check that the date is within the next week
        week_later = now + timedelta(days=7)
        date_matches = re.findall(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:", summary)
        for match in date_matches:
            event_date = datetime.strptime(match, "%Y-%m-%dT%H:%M:")
            assert now <= event_date <= week_later
    finally:
        # Clean up
        await delete_event(event1["id"])
        await delete_event(event2["id"]) 