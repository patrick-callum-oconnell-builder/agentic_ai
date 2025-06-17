from backend.knowledge_graph import KnowledgeGraph, KNOWLEDGE_GRAPH_PROMPT
import json
import logging

def add_preference_to_kg(preference, user_name: str = None):
    """Add a preference to the knowledge graph.
    
    Args:
        preference: Either a string preference, a dict, or a JSON string containing preference details
        user_name: Optional user name to connect the preference to
    """
    kg = KnowledgeGraph()  # Now loads from file if exists
    # Do NOT call parse_prompt here!
    
    if user_name is None:
        user_name = kg.root_person
        
    # Handle different input types
    if isinstance(preference, dict):
        # Extract the actual preference value from dict
        if 'preference' in preference:
            preference = preference['preference']
        elif 'preference_value' in preference:
            preference = preference['preference_value']
        elif 'value' in preference:
            preference = preference['value']
        else:
            # Use the first value in the dict
            preference = next(iter(preference.values()))
    elif isinstance(preference, str):
        # Try to parse as JSON if it looks like JSON
        if preference.strip().startswith('{'):
            try:
                pref_dict = json.loads(preference)
                if isinstance(pref_dict, dict):
                    if 'preference' in pref_dict:
                        preference = pref_dict['preference']
                    elif 'preference_value' in pref_dict:
                        preference = pref_dict['preference_value']
                    elif 'value' in pref_dict:
                        preference = pref_dict['value']
                    else:
                        preference = next(iter(pref_dict.values()))
            except json.JSONDecodeError:
                pass
    
    # Clean up the preference string
    if isinstance(preference, str):
        preference = preference.strip().strip('"\'')
    else:
        preference = str(preference).strip().strip('"\'')
    
    # Add the preference to the KG
    kg._add_entity("PREFERENCE", preference, {"type": "like", "source": "user"})
    kg._add_relation(user_name, preference, "LIKES")
    kg.save_to_file()
    logging.getLogger(__name__).info(f"Preference '{preference}' added to KG for user '{user_name}'")
    return {"status": "success", "preference": preference} 