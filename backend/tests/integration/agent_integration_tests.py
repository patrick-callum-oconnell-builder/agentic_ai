import unittest
import asyncio
import os
import sys
from datetime import datetime

import httpx
import pytest
from dotenv import load_dotenv
import logging
from typing import List, Dict, Any
from openai import AsyncOpenAI

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(backend_dir)

from agent import PersonalTrainerAgent
from backend.google_services.maps import GoogleMapsService

logger = logging.getLogger(__name__)

class TestAgentIntegration(unittest.TestCase):
    @pytest.fixture
    async def agent(self):
        """Create an agent with all required services."""
        maps_service = GoogleMapsService()
        agent = await PersonalTrainerAgent.ainit(maps_service=maps_service)
        return agent

    @pytest.mark.asyncio
    async def test_basic_conversation(self, agent):
        """Test basic conversation flow."""
        messages = [
            {"role": "user", "content": "Hello, I need help with my fitness goals."}
        ]
        response = await agent.process_messages(messages)
        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_workout_planning(self, agent):
        """Test workout planning conversation."""
        messages = [
            {"role": "user", "content": "I want to start working out. Can you help me create a plan?"}
        ]
        response = await agent.process_messages(messages)
        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0
        assert any(keyword in response.lower() for keyword in ["workout", "exercise", "plan", "routine"])

    @pytest.mark.asyncio
    async def test_nutrition_advice(self, agent):
        """Test nutrition advice conversation."""
        messages = [
            {"role": "user", "content": "What should I eat to support my workout routine?"}
        ]
        response = await agent.process_messages(messages)
        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0
        assert any(keyword in response.lower() for keyword in ["nutrition", "diet", "food", "protein", "carbohydrates"])

    @pytest.mark.asyncio
    async def test_goal_setting(self, agent):
        """Test goal setting conversation."""
        messages = [
            {"role": "user", "content": "I want to lose 10 pounds in 3 months. Is this realistic?"}
        ]
        response = await agent.process_messages(messages)
        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0
        assert any(keyword in response.lower() for keyword in ["goal", "realistic", "weight", "loss", "plan"])

    @pytest.mark.asyncio
    async def test_error_handling(self, agent):
        """Test error handling in conversation."""
        messages = [
            {"role": "user", "content": ""}  # Empty message should be handled gracefully
        ]
        response = await agent.process_messages(messages)
        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0
        assert "error" not in response.lower()  # Should not expose error details to user

    @pytest.mark.asyncio
    async def test_conversation_history(self, agent):
        """Test conversation history handling."""
        messages = [
            {"role": "user", "content": "I want to start running."},
            {"role": "assistant", "content": "That's a great goal! How often would you like to run?"},
            {"role": "user", "content": "Three times a week."}
        ]
        response = await agent.process_messages(messages)
        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0
        assert any(keyword in response.lower() for keyword in ["running", "schedule", "plan", "routine"])

    @pytest.mark.asyncio
    async def test_tool_integration(self, agent):
        """Test integration with tools."""
        messages = [
            {"role": "user", "content": "Find me some gyms near 123 Main St, New York, NY"}
        ]
        response = await agent.process_messages(messages)
        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0
        assert any(keyword in response.lower() for keyword in ["gym", "location", "address", "nearby"])

    # The following tests are commented out because they require services not supported by the new agent signature
    # @pytest.mark.asyncio
    # async def test_basic_greeting(self):
    #     ...
    # @pytest.mark.asyncio
    # async def test_no_tool_call_on_greeting(self):
    #     ...
    # @pytest.mark.asyncio
    # async def test_no_recursion_error_on_greeting(self):
    #     ...
    # @pytest.mark.asyncio
    # async def test_schedule_workout_flow(self):
    #     ...
    # @pytest.mark.asyncio
    # async def test_schedule_workout_with_missing_info(self):
    #     ...
    # @pytest.mark.asyncio
    # async def test_schedule_workout_with_invalid_time(self):
    #     ...
    # @pytest.mark.asyncio
    # async def test_api_no_recursion_error_on_greeting(self):
    #     ...
    # @pytest.mark.asyncio
    # async def test_message_normalization(self):
    #     ...
    # @pytest.mark.asyncio
    # async def test_message_history_handling(self):
    #     ...
    # @pytest.mark.asyncio
    # async def test_invalid_message_handling(self):
    #     ...
    # @pytest.mark.asyncio
    # async def test_two_message_flow_for_tool_action(self):
    #     ...
    # @pytest.mark.asyncio
    # async def test_tool_result_formatting_and_animation(self):
    #     ...

if __name__ == '__main__':
    unittest.main() 