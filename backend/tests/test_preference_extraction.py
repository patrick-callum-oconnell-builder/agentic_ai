import pytest
import asyncio
import os
from backend.agent import PersonalTrainerAgent
from backend.knowledge_graph import KnowledgeGraph, KNOWLEDGE_GRAPH_PROMPT
from langchain_core.messages import HumanMessage

@pytest.mark.asyncio
async def test_preference_extraction_and_kg_update():
    """Test that the agent can extract preferences and update the KG."""
    # Remove kg.txt for a clean slate
    kg_file = os.path.join(os.path.dirname(__file__), '../knowledge_graph.py')
    kg_file = os.path.join(os.path.dirname(kg_file), 'kg.txt')
    if os.path.exists(kg_file):
        os.remove(kg_file)

    # Initialize the agent with minimal services (we only need the LLM)
    agent = PersonalTrainerAgent(
        calendar_service=None,
        gmail_service=None,
        tasks_service=None,
        drive_service=None,
        sheets_service=None,
        maps_service=None
    )
    await agent.async_init()

    # Test cases with different preference expressions
    test_cases = [
        "I really enjoy yoga and meditation",
        "I prefer strength training over cardio",
        "I love eating healthy food and doing morning workouts",
        "I'm not interested in running, but I like swimming"
    ]

    for test_input in test_cases:
        # Create a message object
        message = HumanMessage(content=test_input)
        
        # Run the conversation loop
        responses = await agent.agent_conversation_loop(message)
        
        # Verify that we got a response about adding the preference
        assert any("I've added your preference" in response for response in responses), \
            f"Expected preference addition message for input: {test_input}"
        
        # Reload KG to get updated state
        kg = KnowledgeGraph()
        
        # Check that the preference was added as an entity
        preference_entities = [
            entity for entity in kg.entity_map.values()
            if entity.type == "PREFERENCE"
        ]
        assert any(any(word in entity.id.lower() for word in test_input.lower().split()) for entity in preference_entities), \
            f"Preference from input not found in KG entities: {test_input}"
        
        # Check that the preference is connected to the root person
        root_person = kg.root_person
        assert root_person is not None, "Root person not found in KG"
        
        # Get relations from root person
        relations = kg.get_relations(root_person)
        preference_relations = [
            rel for rel in relations
            if rel.type == "LIKES" or rel.type == "PREFERS"
        ]
        assert len(preference_relations) > 0, \
            f"No preference relations found for root person for input: {test_input}"
        
        # Verify the preference is in the relations
        preference_texts = [rel.target for rel in preference_relations]
        assert any(any(word in pref.lower() for word in test_input.lower().split()) for pref in preference_texts), \
            f"Preference from input not found in relations: {test_input}"

if __name__ == "__main__":
    asyncio.run(test_preference_extraction_and_kg_update()) 