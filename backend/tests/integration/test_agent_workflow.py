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
async def test_agent_initialization(agent):
    """Test that the agent initializes properly with all required services."""
    assert agent.calendar_service is not None
    assert agent.gmail_service is not None
    assert agent.tasks_service is not None
    assert agent.drive_service is not None
    assert agent.sheets_service is not None
    assert agent.maps_service is not None

@pytest.mark.asyncio
async def test_tool_creation(agent):
    """Test that all tools are created properly."""
    tools = agent._create_tools()
    assert tools is not None
    assert len(tools) > 0
    tool_names = [tool.name for tool in tools]
    assert "get_calendar_events" in tool_names
    assert "create_calendar_event" in tool_names
    assert "send_email" in tool_names
    assert "create_task" in tool_names
    assert "search_drive" in tool_names

@pytest.mark.asyncio
async def test_agent_workflow_creation(agent):
    """Test that the agent workflow is created properly."""
    workflow = await agent._create_agent_workflow()
    assert workflow is not None
    assert hasattr(workflow, "model_name")
    assert hasattr(workflow, "temperature")
    assert hasattr(workflow, "streaming")

@pytest.mark.asyncio
async def test_conversation_loop(agent):
    """Test the agent's conversation loop functionality."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "Can you help me schedule a workout?"}
    ]
    
    response = await agent.process_messages(messages)
    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 0

@pytest.mark.asyncio
async def test_streaming_conversation(agent):
    """Test the agent's streaming conversation functionality."""
    messages = [
        {"role": "user", "content": "Schedule a workout for tomorrow"}
    ]

    responses = []
    async for response in agent.process_messages_stream(messages):
        responses.append(response)
    
    assert len(responses) > 0
    assert all(isinstance(r, str) for r in responses)

@pytest.mark.asyncio
async def test_tool_execution_workflow(agent):
    """Test the complete tool execution workflow."""
    # Create a test event with a future time to avoid conflicts
    test_time = (datetime.now() + timedelta(days=2)).replace(hour=14, minute=0, second=0, microsecond=0)
    test_message = f"Schedule a workout for {test_time.strftime('%A, %B %d')} at {test_time.strftime('%I:%M %p')}"
    
    response = await agent.process_messages([{"role": "user", "content": test_message}])
    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 0

@pytest.mark.asyncio
async def test_error_handling(agent):
    """Test the agent's error handling capabilities."""
    # Test with invalid input that should trigger error handling
    test_message = "Schedule a workout at invalid_time"
    response = await agent.process_messages([{"role": "user", "content": test_message}])
    
    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 0

@pytest.mark.asyncio
async def test_message_format_handling(agent):
    """Test the agent's handling of different message formats."""
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