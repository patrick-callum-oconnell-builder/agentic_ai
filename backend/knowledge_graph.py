import networkx as nx
from typing import Dict, List, Optional, Tuple, Set
import re
from dataclasses import dataclass
import logging
from collections import defaultdict
import os
import json

logger = logging.getLogger(__name__)

KNOWLEDGE_GRAPH_PROMPT = """
My name is Patrick O'Connell. I am 25. I like pizza. I also like broccoli. I like martial arts. 
My address is 1 Infinite Loop, Cupertino, CA 95014.

For workouts, I prefer strength training."""

@dataclass
class Entity:
    """Represents an entity in the knowledge graph."""
    id: str
    type: str
    attributes: Dict[str, any]

@dataclass
class Relation:
    """Represents a relation between entities in the knowledge graph."""
    source: str
    target: str
    type: str
    attributes: Dict[str, any]

class Pattern:
    """Represents a pattern for extracting entities and relationships."""
    def __init__(self, pattern: str, entity_type: str, relation_type: Optional[str] = None):
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.entity_type = entity_type
        self.relation_type = relation_type

class KnowledgeGraph:
    """A knowledge graph implementation for storing and querying user information."""
    
    # Common patterns for entity and relationship extraction
    ENTITY_PATTERNS = [
        Pattern(r"name is ([\w'\- ]+)", "PERSON", "IS_NAMED"),
        Pattern(r"am (\d+)", "AGE", "HAS_AGE"),
        Pattern(r"like ([\w\s]+)", "PREFERENCE", "LIKES"),
        Pattern(r"have a (\w+), (\w+(?:\s+\w+)*)", "PERSON", "HAS_FAMILY"),
        Pattern(r"address is ([\w\s,]+)", "LOCATION", "LIVES_AT"),
        Pattern(r"prefer ([\w\s]+)", "PREFERENCE", "PREFERS"),
        Pattern(r"workout ([\w\s]+)", "WORKOUT_PREFERENCE", "PREFERS_WORKOUT"),
        Pattern(r"also like ([\w\s]+)", "PREFERENCE", "LIKES"),
    ]
    
    # Common relationship indicators
    RELATIONSHIP_INDICATORS = {
        "is": "IS_A",
        "has": "HAS",
        "likes": "LIKES",
        "prefers": "PREFERS",
        "lives": "LIVES_AT",
        "works": "WORKS_AT",
        "studies": "STUDIES_AT",
        "owns": "OWNS",
        "uses": "USES",
        "needs": "NEEDS",
        "wants": "WANTS",
        "requires": "REQUIRES",
        "have": "HAS",
        "am": "IS_A",
        "enjoys": "ENJOYS",
    }
    
    KG_FILE = os.path.join(os.path.dirname(__file__), 'kg.txt')
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.entity_map: Dict[str, Entity] = {}
        self.relation_map: Dict[Tuple[str, str, str], Relation] = {}
        self.entity_types: Set[str] = set()
        self.relation_types: Set[str] = set()
        self.root_person: Optional[str] = None
        self.patterns = self.ENTITY_PATTERNS.copy()
        self.relationship_indicators = self.RELATIONSHIP_INDICATORS.copy()
        # Always rebuild from prompt
        self.parse_prompt(KNOWLEDGE_GRAPH_PROMPT)
        self.save_to_file()
        
    def save_to_file(self):
        """Persist the KG to a file as JSON."""
        data = {
            'entities': {k: {'type': v.type, 'attributes': v.attributes} for k, v in self.entity_map.items()},
            'relations': [
                {'source': r.source, 'target': r.target, 'type': r.type, 'attributes': r.attributes}
                for r in self.relation_map.values()
            ],
            'root_person': self.root_person
        }
        with open(self.KG_FILE, 'w') as f:
            json.dump(data, f)

    def parse_prompt(self, prompt: str) -> None:
        """Parse the prompt and construct the knowledge graph."""
        # Clear existing data
        self.graph = nx.DiGraph()
        self.entity_map = {}
        self.relation_map = {}
        self.root_person = None
        
        # Split into sentences and clean them
        sentences = [s.strip() for s in prompt.split('.') if s.strip()]
        
        # First pass: identify entities and their types, and extract root person
        for sentence in sentences:
            self._extract_entities(sentence)
            # Try to extract the user's name as root
            if self.root_person is None:
                match = re.search(r"name is ([\w'\- ]+)", sentence, re.IGNORECASE)
                if match:
                    self.root_person = match.group(1).strip()
        
        # Second pass: establish relationships
        for sentence in sentences:
            self._extract_relationships(sentence)
            
        # Save the final state after parsing
        self.save_to_file()
        
    def _extract_entities(self, sentence: str) -> None:
        """Extract entities from a sentence using pattern matching."""
        for pattern in self.patterns:
            matches = pattern.pattern.finditer(sentence)
            for match in matches:
                entity_value = match.group(1).strip()
                # If this is a preference-like pattern, split on 'and' and commas
                if pattern.entity_type in ["PREFERENCE", "WORKOUT_PREFERENCE"]:
                    items = re.split(r",| and ", entity_value)
                    for item in items:
                        item = item.strip()
                        if item:
                            self._add_entity(pattern.entity_type, item, {
                                "type": pattern.entity_type.lower(),
                                "source": "pattern_match"
                            })
                else:
                    self._add_entity(pattern.entity_type, entity_value, {
                        "type": pattern.entity_type.lower(),
                        "source": "pattern_match"
                    })
                # If there's a second group (e.g., for family relationships)
                if len(match.groups()) > 1:
                    related_entity = match.group(2).strip()
                    self._add_entity(pattern.entity_type, related_entity, {
                        "type": pattern.entity_type.lower(),
                        "source": "pattern_match"
                    })
                    
    def _extract_relationships(self, sentence: str) -> None:
        """Extract relationships between entities using natural language patterns."""
        specific_pattern_matched = False
        for pattern in self.patterns:
            if pattern.relation_type:
                matches = pattern.pattern.finditer(sentence)
                for match in matches:
                    if len(match.groups()) == 1:
                        entity_value = match.group(1).strip()
                        # If this is a preference-like pattern, split on 'and' and commas
                        if pattern.entity_type in ["PREFERENCE", "WORKOUT_PREFERENCE"]:
                            items = re.split(r",| and ", entity_value)
                            for item in items:
                                item = item.strip()
                                if item:
                                    if self._is_first_person(sentence) and self.root_person:
                                        subject = self.root_person
                                    else:
                                        subject = self._find_subject_in_context(sentence[:sentence.lower().find(match.group(0))])
                                    if subject:
                                        self._add_relation(subject, item, pattern.relation_type)
                                        specific_pattern_matched = True
                        else:
                            if self._is_first_person(sentence) and self.root_person:
                                subject = self.root_person
                            else:
                                subject = self._find_subject_in_context(sentence[:sentence.lower().find(match.group(0))])
                            if subject:
                                self._add_relation(subject, entity_value, pattern.relation_type)
                                specific_pattern_matched = True
                    elif len(match.groups()) == 2:
                        entity1 = match.group(1).strip()
                        entity2 = match.group(2).strip()
                        self._add_relation(entity1, entity2, pattern.relation_type)
                        specific_pattern_matched = True
        
        # Only apply generic relationship indicators if no specific pattern matched
        if not specific_pattern_matched:
            words = sentence.lower().split()
            for i, word in enumerate(words):
                if word in self.relationship_indicators:
                    relation_type = self.relationship_indicators[word]
                    if i > 0 and i < len(words) - 1:
                        source_entities = self._find_entities_in_context(sentence[:sentence.lower().find(word)])
                        target_entities = self._find_entities_in_context(sentence[sentence.lower().find(word) + len(word):])
                        # If first person and no explicit source, use root_person
                        if self._is_first_person(sentence) and self.root_person and not source_entities:
                            source_entities = [self.root_person]
                        for source in source_entities:
                            for target in target_entities:
                                self._add_relation(source, target, relation_type)
    
    def _is_first_person(self, sentence: str) -> bool:
        """Check if the sentence is about the first person (I, my, me)."""
        return bool(re.search(r"\b(I|my|me|mine)\b", sentence, re.IGNORECASE))
        
    def _find_subject_in_context(self, context: str) -> Optional[str]:
        """Find the subject of a sentence in the given context."""
        # Look for the first person entity in the context
        for entity_id, entity in self.entity_map.items():
            if entity.type == "PERSON" and entity_id.lower() in context.lower():
                return entity_id
        return None
        
    def _find_entities_in_context(self, context: str) -> List[str]:
        """Find known entities in a given context."""
        found_entities = []
        for entity_id in self.entity_map:
            if entity_id.lower() in context.lower():
                found_entities.append(entity_id)
        return found_entities
        
    def _add_entity(self, entity_type: str, entity_id: str, attributes: Dict[str, any]) -> None:
        """Add an entity to the knowledge graph."""
        if entity_id not in self.entity_map:
            entity = Entity(id=entity_id, type=entity_type, attributes=attributes)
            self.entity_map[entity_id] = entity
            self.graph.add_node(entity_id, **{"type": entity_type, **attributes})
            self.entity_types.add(entity_type)
            self.save_to_file()  # Save after adding entity
            
    def _add_relation(self, source: str, target: str, relation_type: str, attributes: Dict[str, any] = None) -> None:
        """Add a relation to the knowledge graph."""
        if attributes is None:
            attributes = {}
        key = (source, target, relation_type)
        if key not in self.relation_map:
            relation = Relation(source=source, target=target, type=relation_type, attributes=attributes)
            self.relation_map[key] = relation
            self.graph.add_edge(source, target, **{"type": relation_type, **attributes})
            self.relation_types.add(relation_type)
            self.save_to_file()  # Save after adding relation
            
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get an entity by its ID."""
        return self.entity_map.get(entity_id)
        
    def get_relations(self, entity_id: str) -> List[Relation]:
        """Get all relations where the given entity is the source."""
        return [r for r in self.relation_map.values() if r.source == entity_id]
        
    def query(self, entity_type: Optional[str] = None, relation_type: Optional[str] = None) -> List[Tuple[Entity, Relation, Entity]]:
        """Query the knowledge graph for entities and relations matching the given criteria."""
        results = []
        for source, target, data in self.graph.edges(data=True):
            source_entity = self.entity_map.get(source)
            target_entity = self.entity_map.get(target)
            if source_entity and target_entity:
                if entity_type and target_entity.type != entity_type:
                    continue
                if relation_type and data.get('type') != relation_type:
                    continue
                relation = self.relation_map.get((source, target, data.get('type')))
                if relation:
                    results.append((source_entity, relation, target_entity))
        return results
        
    def add_pattern(self, pattern: str, entity_type: str, relation_type: Optional[str] = None) -> None:
        """Add a new pattern for entity and relationship extraction."""
        self.patterns.append(Pattern(pattern, entity_type, relation_type))
        
    def add_relationship_indicator(self, indicator: str, relation_type: str) -> None:
        """Add a new relationship indicator."""
        self.relationship_indicators[indicator] = relation_type

    def to_dict(self) -> dict:
        """Return a serializable dictionary of all entities and relations."""
        return {
            "entities": {k: {"type": v.type, "attributes": v.attributes} for k, v in self.entity_map.items()},
            "relations": [
                {"source": r.source, "target": r.target, "type": r.type, "attributes": r.attributes}
                for r in self.relation_map.values()
            ]
        }

# Example usage
if __name__ == "__main__":
    kg = KnowledgeGraph()
    
    # Add some custom patterns
    kg.add_pattern(r"works at ([\w\s]+)", "ORGANIZATION", "WORKS_AT")
    kg.add_pattern(r"studies ([\w\s]+)", "SUBJECT", "STUDIES")
    
    # Add some custom relationship indicators
    kg.add_relationship_indicator("enjoys", "ENJOYS")
    kg.add_relationship_indicator("practices", "PRACTICES")
    
    # Print all entities
    print("\nEntities:")
    for entity_id, entity in kg.entity_map.items():
        print(f"{entity_id} ({entity.type}): {entity.attributes}")
    
    # Print all relations
    print("\nRelations:")
    for relation in kg.relation_map.values():
        print(f"{relation.source} --[{relation.type}]--> {relation.target}")
    
    # Print available entity and relation types
    print("\nAvailable Entity Types:", kg.entity_types)
    print("Available Relation Types:", kg.relation_types)