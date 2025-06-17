import os
import sys
import pytest
from langchain_core.messages import HumanMessage
from backend.tests.unit.test_utils import llm_check_response_intent

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

@pytest.mark.asyncio
async def test_fetch_upcoming_events(agent):
    """Test fetching upcoming events."""
    # Explicitly await the agent fixture
    agent_instance = await agent
    try:
        # Fetch upcoming events using the agent's calendar service
        events = await agent_instance.calendar_service.get_upcoming_events()
        assert isinstance(events, list)
        print(f"Calendar test: Successfully fetched {len(events)} upcoming events")
    except Exception as e:
        pytest.fail(f"Failed to fetch upcoming events: {str(e)}")
        
@pytest.mark.asyncio
async def test_schedule_workout(agent):
    """Test scheduling a workout."""
    # Explicitly await the agent fixture
    agent_instance = await agent
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
        result = await agent_instance.calendar_service.write_event(workout)
        assert result is not None
        assert 'id' in result
        print(f"Calendar test: Successfully scheduled workout")
    except Exception as e:
        pytest.fail(f"Failed to schedule workout: {str(e)}")

@pytest.mark.asyncio
async def test_tool_confirmation_and_response(agent):
    """Test that a tool call yields a confirmation and tool result in a single user-friendly message."""
    # Explicitly await the agent fixture
    agent_instance = await agent
    user_message = HumanMessage(content="Add a workout to my calendar for tomorrow at 10am called 'Test Workout'.")
    responses = await agent_instance.process_messages([user_message])
    if isinstance(responses, str):
        messages = [responses]
    elif isinstance(responses, list):
        messages = responses
    else:
        pytest.fail(f"Unexpected response type: {type(responses)}")
    
    # The agent should return a single consolidated message that confirms the action and provides the result
    assert len(messages) >= 1, f"Expected at least 1 message, got {len(messages)}: {messages}"
    
    # Check that the response contains confirmation and result information
    response_text = messages[0] if isinstance(messages[0], str) else str(messages[0])
    assert "successfully added" in response_text.lower() or "added to your calendar" in response_text.lower()
    assert "calendar" in response_text.lower()
    assert "10" in response_text or "tomorrow" in response_text.lower()

@pytest.mark.asyncio
async def test_calendar_query_returns_friendly_response(agent):
    # Explicitly await the agent fixture
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
    pytest.main() 