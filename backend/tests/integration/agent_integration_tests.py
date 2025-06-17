import unittest
import os
import sys
from dotenv import load_dotenv
import pytest
import asyncio
from datetime import datetime
import httpx
from langchain_core.messages import HumanMessage

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(backend_dir)

from agent import PersonalTrainerAgent
from backend.google_services.calendar import GoogleCalendarService
from backend.google_services.gmail import GoogleGmailService
from backend.google_services.tasks import GoogleTasksService
from backend.google_services.drive import GoogleDriveService
from backend.google_services.sheets import GoogleSheetsService
from backend.google_services.maps import GoogleMapsService

class TestAgentIntegration(unittest.TestCase):
    async def asyncSetUp(self):
        """Set up test fixtures before each test method."""
        load_dotenv()
        
        # Get the Google Maps API key from environment variables
        maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not maps_api_key:
            raise ValueError("Missing required environment variable: GOOGLE_MAPS_API_KEY")
        
        self.agent = PersonalTrainerAgent(
            calendar_service=GoogleCalendarService(),
            gmail_service=GoogleGmailService(),
            tasks_service=GoogleTasksService(),
            drive_service=GoogleDriveService(),
            sheets_service=GoogleSheetsService(),
            maps_service=GoogleMapsService(api_key=maps_api_key)
        )
        await self.agent.async_init()

    def setUp(self):
        """Synchronous wrapper for async setup."""
        asyncio.run(self.asyncSetUp())

    @pytest.mark.asyncio
    async def test_basic_greeting(self):
        """Test that the agent can handle a basic greeting without errors."""
        messages = [{"role": "user", "content": "Hi, how are you?"}]
        response = await self.agent.process_messages(messages)
        print(f"Agent response: {response}")
        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)
        self.assertNotIn("error", response.lower(), "Response should not contain the word 'error'")
        self.assertNotEqual(response, "No response generated", "Agent should not return 'No response generated'")

    @pytest.mark.asyncio
    async def test_no_tool_call_on_greeting(self):
        """Test that a simple greeting does not trigger a tool call and returns a direct LLM response."""
        messages = [{"role": "user", "content": "hello"}]
        response = await self.agent.process_messages(messages)
        print(f"Agent response: {response}")
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)
        self.assertNotIn("Tool result:", response, "Greeting should not trigger a tool call.")
        self.assertNotIn("error", response.lower(), "Response should not contain the word 'error'")
        self.assertNotEqual(response, "No response generated", "Agent should not return 'No response generated'")

    @pytest.mark.asyncio
    async def test_no_recursion_error_on_greeting(self):
        """Test that a simple greeting does not cause a recursion error or failure."""
        messages = [{"role": "user", "content": "hello"}]
        response = await self.agent.process_messages(messages)
        print(f"Agent response: {response}")
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)
        self.assertNotIn("recursion", response.lower(), "Greeting should not cause a recursion error.")
        self.assertNotIn("error", response.lower(), "Greeting should not cause an error.")
        self.assertNotIn("couldn't process", response.lower(), "Greeting should not cause a processing error.")

    @pytest.mark.asyncio
    async def test_schedule_workout_flow(self):
        """Test the complete flow of scheduling a workout."""
        test_message = "Schedule a workout for tonight at 10pm, 1 hour long"
        response = await self.agent.process_messages([{"role": "user", "content": test_message}])
        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)
        events = await self.agent.calendar_service.get_events_for_date(datetime.now().date())
        self.assertTrue(len(events) > 0)
        workout_event = None
        for event in events:
            if "workout" in event["summary"].lower():
                workout_event = event
                break
        self.assertIsNotNone(workout_event, "No workout event found in calendar")
        print(f"Found workout event: {workout_event}")

    @pytest.mark.asyncio
    async def test_schedule_workout_with_missing_info(self):
        """Test scheduling a workout with missing information."""
        test_message = "Schedule a workout for tonight"
        response = await self.agent.process_messages([{"role": "user", "content": test_message}])
        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)
        self.assertTrue("time" in response.lower() or "when" in response.lower())
        events = await self.agent.calendar_service.get_events_for_date(datetime.now().date())
        for event in events:
            self.assertNotEqual(event["summary"], "Evening Workout")

    @pytest.mark.asyncio
    async def test_schedule_workout_with_invalid_time(self):
        """Test scheduling a workout with invalid time format."""
        test_message = "Schedule a workout for tonight at sometime"
        response = await self.agent.process_messages([{"role": "user", "content": test_message}])
        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)
        self.assertTrue("time" in response.lower() or "format" in response.lower())
        events = await self.agent.calendar_service.get_events_for_date(datetime.now().date())
        for event in events:
            self.assertNotEqual(event["summary"], "Evening Workout")

    @pytest.mark.asyncio
    async def test_api_no_recursion_error_on_greeting(self):
        """Test the /api/chat endpoint with a greeting to ensure no recursion error occurs."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            payload = {"messages": [{"role": "user", "content": "hello"}]}
            response = await client.post("/api/chat", json=payload)
            assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
            data = response.json()
            agent_response = data.get("response", "")
            print(f"API Agent response: {agent_response}")
            assert isinstance(agent_response, str)
            assert len(agent_response) > 0
            assert "recursion" not in agent_response.lower(), "Greeting should not cause a recursion error."
            assert "error" not in agent_response.lower(), "Greeting should not cause an error."
            assert "couldn't process" not in agent_response.lower(), "Greeting should not cause a processing error."

    @pytest.mark.asyncio
    async def test_message_normalization(self):
        """Test that messages are normalized consistently."""
        test_cases = [
            # Test case: (input_message, expected_normalized)
            (
                {"role": "USER", "content": "  Hello  "},
                {"role": "user", "content": "Hello"}
            ),
            (
                {"role": "assistant", "content": "  Hi there!  "},
                {"role": "assistant", "content": "Hi there!"}
            ),
            (
                {"role": "SYSTEM", "content": "  System message  "},
                {"role": "system", "content": "System message"}
            ),
            (
                {"role": "invalid", "content": "Test"},
                {"role": "user", "content": "Test"}
            )
        ]
        
        for input_msg, expected in test_cases:
            # Test direct agent processing
            response = await self.agent.process_messages([input_msg])
            self.assertIsNotNone(response)
            self.assertIsInstance(response, str)
            self.assertTrue(len(response) > 0)
            
            # Test API endpoint
            async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
                payload = {"messages": [input_msg]}
                response = await client.post("/api/chat", json=payload)
                assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
                data = response.json()
                assert isinstance(data.get("response"), str)
                assert len(data["response"]) > 0

    @pytest.mark.asyncio
    async def test_message_history_handling(self):
        """Test that message history is handled consistently."""
        # Test with a conversation history
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ]
        
        # Test direct agent processing
        response = await self.agent.process_messages(messages)
        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)
        
        # Test API endpoint
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            payload = {"messages": messages}
            response = await client.post("/api/chat", json=payload)
            assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
            data = response.json()
            assert isinstance(data.get("response"), str)
            assert len(data["response"]) > 0

    @pytest.mark.asyncio
    async def test_invalid_message_handling(self):
        """Test handling of invalid messages."""
        test_cases = [
            # Test case: (input_message, expected_status_code)
            ({"role": "user"}, 400),  # Missing content
            ({"content": "Hello"}, 400),  # Missing role
            ({"role": "user", "content": ""}, 400),  # Empty content
            ({"role": "user", "content": "   "}, 400),  # Whitespace content
            ({"role": 123, "content": "Hello"}, 400),  # Invalid role type
            ({"role": "user", "content": 123}, 400),  # Invalid content type
        ]
        
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            for input_msg, expected_status in test_cases:
                payload = {"messages": [input_msg]}
                response = await client.post("/api/chat", json=payload)
                assert response.status_code == expected_status, \
                    f"Expected status {expected_status} for input {input_msg}, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_two_message_flow_for_tool_action(self):
        """Test that the agent returns two distinct assistant messages (intent and outcome) for a tool action."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            payload = {"messages": [{"role": "user", "content": "Please schedule a workout for tomorrow at 10am."}]}
            response = await client.post("/api/chat", json=payload)
            assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
            data = response.json()
            agent_response = data.get("response", "")
            print(f"API Agent response: {agent_response}")
            # The backend should return both the intent and the outcome as two assistant messages
            # We expect the response to contain both an intent/acknowledgment and a confirmation/outcome
            # For robustness, check for two non-empty assistant messages separated by the tool result marker or by a delay
            # The new backend logic includes '[TOOL RESULT]:' as a marker
            assert '[TOOL RESULT]:' in agent_response, "Response should include a tool result marker."
            # Split on the marker and check both parts are non-empty
            parts = agent_response.split('[TOOL RESULT]:')
            assert len(parts) >= 2, "Response should contain at least two parts (intent and outcome)."
            intent = parts[0].strip()
            outcome = ''.join(parts[1:]).strip()
            assert len(intent) > 0, "Intent message should not be empty."
            assert len(outcome) > 0, "Outcome message should not be empty."
            # Optionally, check that the intent is an acknowledgment and the outcome is a confirmation
            assert any(word in intent.lower() for word in ["i'll", "i will", "let me", "scheduling", "adding", "sure"]), "Intent should acknowledge the action."
            assert any(word in outcome.lower() for word in ["scheduled", "added", "created", "workout", "success", "confirmed"]), "Outcome should confirm the result."

if __name__ == '__main__':
    unittest.main() 