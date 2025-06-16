import os
import sys
import pytest
import asyncio
import logging
from dotenv import load_dotenv
from openai import AsyncOpenAI
from backend.tests.integration.google_services.base_maps_integration import BaseMapsIntegrationTest
from backend.agent import PersonalTrainerAgent
from backend.google_services.maps import GoogleMapsService
from backend.google_services.calendar import GoogleCalendarService
from backend.google_services.gmail import GoogleGmailService
from backend.google_services.tasks import GoogleTasksService
from backend.google_services.drive import GoogleDriveService
from backend.google_services.sheets import GoogleSheetsService

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_debug.log')
    ]
)
logger = logging.getLogger(__name__)

async def evaluate_response_with_llm(response: str) -> bool:
    """Evaluate if the response is valid using LLM."""
    client = AsyncOpenAI()
    
    # Log the full response being evaluated
    logger.debug(f"Full response being evaluated:\n{response}")
    
    # Create the evaluation prompt
    evaluation_prompt = f"""You are evaluating a response from a personal trainer agent about finding workout locations.
The response should either:
1. Contain specific workout locations or gyms (names and addresses), OR
2. Show that the agent is using the Google Maps service to search for locations (e.g., mentioning searching, looking up, or finding places)

Here is the response to evaluate:
{response}

Respond with exactly one word: 'VALID' if the response meets either criteria, or 'INVALID' if it doesn't."""
    
    # Log the evaluation prompt
    logger.debug(f"LLM evaluation prompt: {evaluation_prompt}")
    
    # Get LLM's evaluation
    result = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an evaluator. Respond with exactly one word: 'VALID' or 'INVALID'."},
            {"role": "user", "content": evaluation_prompt}
        ],
        temperature=0
    )
    
    # Log the raw result
    logger.debug(f"LLM evaluation raw result: {result}")
    
    # Parse the result
    evaluation = result.choices[0].message.content.strip().upper()
    logger.debug(f"LLM evaluation parsed result: {evaluation}")
    
    return evaluation == "VALID"

class TestMapsIntegration(BaseMapsIntegrationTest):
    @pytest.mark.asyncio
    async def test_direct_tool_node_invocation(self):
        """Test direct tool node invocation with valid address."""
        agent = await PersonalTrainerAgent.ainit(self.maps_service)
        tool_call = {
            "tool_name": "GoogleMaps",
            "tool_args": {
                "action": "find_workout_locations",
                "address": "123 Main St, New York, NY",
                "radius": 3218
            }
        }
        result = await agent.tool_node(tool_call)
        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(place, dict) for place in result)
        assert all("name" in place and "address" in place for place in result)

    @pytest.mark.asyncio
    async def test_agent_workflow(self):
        """Test the complete agent workflow with maps integration."""
        agent = await PersonalTrainerAgent.ainit(self.maps_service)
        messages = [
            {"role": "user", "content": "Find me some gyms near 123 Main St, New York, NY"}
        ]
        response = await agent.process_messages(messages)
        assert response is not None
        assert isinstance(response, str)
        assert await evaluate_response_with_llm(response)

if __name__ == '__main__':
    pytest.main() 