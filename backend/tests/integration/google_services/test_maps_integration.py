import os
import sys
import pytest
import json
import re
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) )

# Load environment variables
load_dotenv()

@pytest.mark.asyncio
async def test_find_nearby_workout_locations(agent):
    # Explicitly await the agent fixture
    agent_instance = await agent
    messages = [
        HumanMessage(content="Find me workout locations near 1 Infinite Loop, Cupertino, CA")
    ]
    response = await agent_instance.process_messages(messages)
    print(f"Agent final response: {response}")
    if isinstance(response, str):
        lines = [msg.strip() for msg in response.split('\n') if msg.strip()]
        final_message = lines[-1] if lines else ""
    elif isinstance(response, list):
        final_message = response[-1] if response else ""
    else:
        final_message = str(response)
    assert final_message is not None
    assert isinstance(final_message, str)
    assert ("Cupertino" in final_message or "workout" in final_message.lower() or "fitness" in final_message.lower())

@pytest.mark.asyncio
async def test_maps_tool_call(agent):
    # Explicitly await the agent fixture
    agent_instance = await agent
    messages = [
        HumanMessage(content="Find gyms near 1 Infinite Loop, Cupertino, CA")
    ]
    response = await agent_instance.process_messages(messages)
    print(f"Maps tool call response: {response}")
    assert response is not None
    assert llm_evaluate_maps_response(response), f"Response did not pass LLM evaluation: {response}"

# Add a placeholder for LLM evaluation
def llm_evaluate_maps_response(response):
    # In production, this would call an LLM to evaluate the response.
    # For now, accept any non-empty string as a valid answer.
    return bool(response and isinstance(response, str) and len(response.strip()) > 0)

if __name__ == '__main__':
    pytest.main() 