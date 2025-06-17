import pytest
from langchain.schema import HumanMessage

@pytest.mark.asyncio
async def test_find_nearby_gyms_natural_language(agent):
    """Test that the agent can handle natural language queries about finding nearby gyms."""
    # Await the agent fixture
    agent_instance = await agent
    
    # Create a natural language query about finding gyms
    messages = [
        HumanMessage(content="Can you find me some gyms near Apple's Infinite Loop in Cupertino? I'm looking for places within 30 miles.")
    ]
    
    # Process the message
    response = await agent_instance.process_messages(messages)
    
    # Verify the response
    assert response is not None
    assert isinstance(response, str)
    
    # Check that the response contains expected elements
    # We use a relaxed evaluation since the exact response may vary
    response_lower = response.lower()
    assert any(keyword in response_lower for keyword in [
        "gym", "fitness", "workout", "location", "nearby", "cupertino"
    ]), "Response should mention gyms or fitness locations"
    
    # Check that the response includes some form of location information
    assert any(keyword in response_lower for keyword in [
        "address", "street", "avenue", "road", "boulevard", "way"
    ]), "Response should include address information"
    
    # Check that the response includes ratings if available
    assert "rating" in response_lower, "Response should include rating information"
    
    # Verify that the response is properly formatted
    assert "\n" in response, "Response should be formatted with line breaks"
    assert "- " in response, "Response should use bullet points for locations" 