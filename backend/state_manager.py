from typing import Dict, Any, Optional
import json
import os

class StateManager:
    """Manages the state of the agent's conversation and workflow."""
    
    def __init__(self):
        self.state_file = "agent_state.json"
        self.state: Dict[str, Any] = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load the current state from the state file."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_state(self):
        """Save the current state to the state file."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f)
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a value from the state."""
        return self.state.get(key, default)
    
    def set_state(self, key: str, value: Any):
        """Set a value in the state."""
        self.state[key] = value
        self._save_state()
    
    def clear_state(self):
        """Clear all state."""
        self.state = {}
        self._save_state() 