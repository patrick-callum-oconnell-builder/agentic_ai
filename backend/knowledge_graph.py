import networkx as nx
from typing import Dict, List, Optional, Tuple, Set
import re
from dataclasses import dataclass
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

KNOWLEDGE_GRAPH_PROMPT = """
My name is Patrick O'Connell. I am 25. I like pizza. I also like broccoli. I like martial arts. 
I have a sister, Margaret. My address is 1 Infinite Loop, Cupertino, CA 95014.

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
        Pattern(r"name is (\w+(?:\s+\w+)*)", "PERSON", "IS_NAMED"),
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
    }
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.entity_map: Dict[str, Entity] = {}
        self.relation_map: Dict[Tuple[str, str, str], Relation] = {}
        self.entity_types: Set[str] = set()
        self.relation_types: Set[str] = set()
        self.root_person: Optional[str] = None  # Store the user's name
        
    def parse_prompt(self, prompt: str) -> None:
        """Parse the prompt and construct the knowledge graph."""
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
        # Ensure the root person node is always present
        if self.root_person and self.root_person not in self.entity_map:
            self._add_entity("PERSON", self.root_person, {"type": "user", "source": "root"})
        
        # Second pass: establish relationships
        for sentence in sentences:
            self._extract_relationships(sentence)
            
    def _extract_entities(self, sentence: str) -> None:
        """Extract entities from a sentence using pattern matching."""
        for pattern in self.ENTITY_PATTERNS:
            # Skip IS_NAMED pattern for root person
            if pattern.relation_type == "IS_NAMED":
                continue
            matches = pattern.pattern.finditer(sentence)
            for match in matches:
                # Extract the main entity
                entity_value = match.group(1).strip()
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
        for pattern in self.ENTITY_PATTERNS:
            # Custom handling for family relationships
            if pattern.relation_type == "HAS_FAMILY":
                matches = pattern.pattern.finditer(sentence)
                for match in matches:
                    if len(match.groups()) == 2 and self.root_person:
                        # Always relate the root person to the family member with 'RELATED_TO'
                        entity2 = match.group(2).strip()
                        self._add_relation(self.root_person, entity2, "RELATED_TO")
                        specific_pattern_matched = True
                continue
            # Skip IS_NAMED pattern
            if pattern.relation_type == "IS_NAMED":
                continue
            if pattern.relation_type:
                matches = pattern.pattern.finditer(sentence)
                for match in matches:
                    if len(match.groups()) == 1:
                        entity_value = match.group(1).strip()
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
                if word in self.RELATIONSHIP_INDICATORS:
                    relation_type = self.RELATIONSHIP_INDICATORS[word]
                    if i > 0 and i < len(words) - 1:
                        source_entities = self._find_entities_in_context(sentence[:sentence.lower().find(word)])
                        target_entities = self._find_entities_in_context(sentence[sentence.lower().find(word) + len(word):])
                        # If first person and no explicit source, use root_person
                        if self._is_first_person(sentence) and self.root_person and not source_entities:
                            source_entities = [self.root_person]
                        for source in source_entities:
                            for target in target_entities:
                                # Prevent IS_A from root to their own name or substring
                                if relation_type == "IS_A" and self.root_person:
                                    if target == self.root_person or target in self.root_person or self.root_person in target:
                                        continue
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
            
    def _add_relation(self, source: str, target: str, relation_type: str, attributes: Dict[str, any] = None) -> None:
        """Add a relation to the knowledge graph."""
        if attributes is None:
            attributes = {}
            
        relation = Relation(source=source, target=target, type=relation_type, attributes=attributes)
        key = (source, target, relation_type)
        
        if key not in self.relation_map:
            self.relation_map[key] = relation
            self.graph.add_edge(source, target, **{"type": relation_type, **attributes})
            self.relation_types.add(relation_type)
            
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get an entity by its ID."""
        return self.entity_map.get(entity_id)
        
    def get_relations(self, entity_id: str) -> List[Relation]:
        """Get all relations for an entity."""
        return [rel for rel in self.relation_map.values() 
                if rel.source == entity_id or rel.target == entity_id]
        
    def query(self, entity_type: Optional[str] = None, relation_type: Optional[str] = None) -> List[Tuple[Entity, Relation, Entity]]:
        """Query the knowledge graph for specific entity and relation types."""
        results = []
        
        for source, target, data in self.graph.edges(data=True):
            if relation_type and data.get('type') != relation_type:
                continue
                
            source_entity = self.entity_map.get(source)
            target_entity = self.entity_map.get(target)
            
            if entity_type:
                if source_entity and source_entity.type != entity_type:
                    continue
                if target_entity and target_entity.type != entity_type:
                    continue
                    
            if source_entity and target_entity:
                relation = self.relation_map.get((source, target, data.get('type')))
                if relation:
                    results.append((source_entity, relation, target_entity))
                    
        return results
        
    def to_dict(self) -> Dict:
        """Convert the knowledge graph to a dictionary representation, only including the subgraph connected to the root person."""
        if self.root_person and self.root_person in self.graph:
            # Get all nodes in the connected component containing the root person
            connected_nodes = nx.node_connected_component(self.graph.to_undirected(), self.root_person)
            # Filter entities and relations
            entities = {id: {"type": e.type, "attributes": e.attributes}
                        for id, e in self.entity_map.items() if id in connected_nodes}
            relations = {f"{r.source}_{r.target}_{r.type}": {
                "source": r.source,
                "target": r.target,
                "type": r.type,
                "attributes": r.attributes
            } for r in self.relation_map.values() if r.source in connected_nodes and r.target in connected_nodes}
            return {"entities": entities, "relations": relations}
        else:
            # Fallback: return the full graph
            return {
                "entities": {id: {"type": e.type, "attributes": e.attributes} 
                            for id, e in self.entity_map.items()},
                "relations": {f"{r.source}_{r.target}_{r.type}": {
                    "source": r.source,
                    "target": r.target,
                    "type": r.type,
                    "attributes": r.attributes
                } for r in self.relation_map.values()}
            }
        
    def add_pattern(self, pattern: str, entity_type: str, relation_type: Optional[str] = None) -> None:
        """Add a new pattern for entity and relationship extraction."""
        self.ENTITY_PATTERNS.append(Pattern(pattern, entity_type, relation_type))
        
    def add_relationship_indicator(self, indicator: str, relation_type: str) -> None:
        """Add a new relationship indicator."""
        self.RELATIONSHIP_INDICATORS[indicator.lower()] = relation_type.upper()

# Example usage
if __name__ == "__main__":
    kg = KnowledgeGraph()
    
    # Add some custom patterns
    kg.add_pattern(r"works at ([\w\s]+)", "ORGANIZATION", "WORKS_AT")
    kg.add_pattern(r"studies ([\w\s]+)", "SUBJECT", "STUDIES")
    
    # Add some custom relationship indicators
    kg.add_relationship_indicator("enjoys", "ENJOYS")
    kg.add_relationship_indicator("practices", "PRACTICES")
    
    # Parse the prompt
    kg.parse_prompt(KNOWLEDGE_GRAPH_PROMPT)
    
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