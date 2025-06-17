import pytest
from backend.knowledge_graph import KnowledgeGraph, Entity, Relation
import os
import json

@pytest.fixture
def kg():
    """Create a fresh KnowledgeGraph instance for each test."""
    # Create a temporary file for testing
    test_file = "test_kg.txt"
    kg = KnowledgeGraph()
    kg.KG_FILE = test_file
    yield kg
    # Cleanup after tests
    if os.path.exists(test_file):
        os.remove(test_file)

def test_entity_creation(kg):
    """Test creating and retrieving entities."""
    kg._add_entity("PERSON", "John", {"age": 30})
    entity = kg.get_entity("John")
    assert entity is not None
    assert entity.type == "PERSON"
    assert entity.attributes["age"] == 30

def test_relation_creation(kg):
    """Test creating and retrieving relations."""
    kg._add_entity("PERSON", "John", {})
    kg._add_entity("FOOD", "Pizza", {})
    kg._add_relation("John", "Pizza", "LIKES")
    
    relations = kg.get_relations("John")
    assert len(relations) == 1
    assert relations[0].type == "LIKES"
    assert relations[0].target == "Pizza"

def test_prompt_parsing(kg):
    """Test parsing a prompt and extracting entities and relations."""
    prompt = "My name is John. I am 30. I like pizza and martial arts."
    kg.parse_prompt(prompt)
    
    # Check root person
    assert kg.root_person == "John"
    
    # Check entities
    assert "John" in kg.entity_map
    assert "pizza" in kg.entity_map
    assert "martial arts" in kg.entity_map
    
    # Check relations
    relations = kg.get_relations("John")
    assert any(r.type == "LIKES" and r.target == "pizza" for r in relations)
    assert any(r.type == "LIKES" and r.target == "martial arts" for r in relations)

def test_persistence(kg):
    """Test saving and loading the knowledge graph."""
    # Add some data
    kg._add_entity("PERSON", "John", {"age": 30})
    kg._add_entity("FOOD", "Pizza", {})
    kg._add_relation("John", "Pizza", "LIKES")
    
    # Save to file
    kg.save_to_file()
    
    # Create new instance and load
    new_kg = KnowledgeGraph()
    new_kg.KG_FILE = kg.KG_FILE
    new_kg.load_from_file()
    
    # Verify data was loaded correctly
    assert "John" in new_kg.entity_map
    assert "Pizza" in new_kg.entity_map
    relations = new_kg.get_relations("John")
    assert any(r.type == "LIKES" and r.target == "Pizza" for r in relations)

def test_query_method(kg):
    """Test the query method for finding entities and relations."""
    # Add test data
    kg._add_entity("PERSON", "John", {})
    kg._add_entity("FOOD", "Pizza", {})
    kg._add_entity("FOOD", "Burger", {})
    kg._add_relation("John", "Pizza", "LIKES")
    kg._add_relation("John", "Burger", "LIKES")
    
    # Query all FOOD entities
    results = kg.query(entity_type="FOOD")
    assert len(results) == 2
    
    # Query all LIKES relations
    results = kg.query(relation_type="LIKES")
    assert len(results) == 2
    
    # Query specific combination
    results = kg.query(entity_type="FOOD", relation_type="LIKES")
    assert len(results) == 2

def test_pattern_matching(kg):
    """Test the pattern matching functionality."""
    # Add a custom pattern
    kg.add_pattern(r"enjoys ([\w\s]+)", "ACTIVITY", "ENJOYS")
    
    # Test pattern matching
    sentence = "John enjoys swimming"
    kg._extract_entities(sentence)
    kg._extract_relationships(sentence)
    
    assert "swimming" in kg.entity_map
    relations = kg.get_relations("John")
    assert any(r.type == "ENJOYS" and r.target == "swimming" for r in relations)

def test_relationship_indicators(kg):
    """Test the relationship indicator functionality."""
    # Add a custom relationship indicator
    kg.add_relationship_indicator("enjoys", "ENJOYS")
    
    # Test relationship extraction
    sentence = "John enjoys swimming"
    kg._extract_relationships(sentence)
    
    relations = kg.get_relations("John")
    assert any(r.type == "ENJOYS" and r.target == "swimming" for r in relations) 