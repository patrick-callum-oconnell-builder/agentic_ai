from typing import List, Optional, Any, Dict, Annotated
from langchain_core.messages import BaseMessage
import asyncio
from dataclasses import dataclass, field
import operator

def last(left, right):
    return right

@dataclass
class AgentState:
    messages: Annotated[List[BaseMessage], operator.add] = field(default_factory=list)
    status: Annotated[str, last] = "active"
    missing_fields: Annotated[List[str], operator.add] = field(default_factory=list)
    last_tool_result: Annotated[Any, last] = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self):
        self._validate_messages(self.messages)
        self._validate_status(self.status)
        self._validate_missing_fields(self.missing_fields)

    def _validate_messages(self, messages):
        if messages is not None and not isinstance(messages, list):
            raise ValueError("Messages must be a list")
        if messages is not None and not all(isinstance(m, BaseMessage) for m in messages):
            raise ValueError("All messages must be BaseMessage instances")

    def _validate_status(self, status):
        valid_statuses = ["active", "awaiting_user", "awaiting_tool", "error", "done"]
        if status not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")

    def _validate_missing_fields(self, missing_fields):
        if missing_fields is not None and not isinstance(missing_fields, list):
            raise ValueError("Missing fields must be a list")

    async def update(self, **kwargs):
        """Thread-safe state update method."""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    if key == 'messages':
                        self._validate_messages(value)
                    elif key == 'status':
                        self._validate_status(value)
                    elif key == 'missing_fields':
                        self._validate_missing_fields(value)
                    setattr(self, key, value)

    def __getitem__(self, key: str) -> Any:
        """Get an item using dictionary-style access."""
        if not hasattr(self, key):
            raise KeyError(f"AgentState has no attribute '{key}'")
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Set an item using dictionary-style access."""
        if not hasattr(self, key):
            raise KeyError(f"AgentState has no attribute '{key}'")
        setattr(self, key, value)

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the state."""
        return hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        """Get an item with a default value if the key doesn't exist."""
        return getattr(self, key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the state to a dictionary."""
        return {
            "messages": self.messages,
            "status": self.status,
            "missing_fields": self.missing_fields,
            "last_tool_result": self.last_tool_result,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'AgentState':
        """Create a state from a dictionary, ensuring messages are BaseMessage objects."""
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
        def to_message(obj):
            if isinstance(obj, BaseMessage):
                return obj
            if not isinstance(obj, dict):
                return obj
            role = obj.get('role')
            if role == 'user':
                return HumanMessage(**obj)
            elif role == 'assistant':
                return AIMessage(**obj)
            elif role == 'system':
                return SystemMessage(**obj)
            else:
                return BaseMessage(**obj)
        messages = d.get("messages", [])
        messages = [to_message(m) for m in messages]
        return cls(
            messages=messages,
            status=d.get("status", "active"),
            missing_fields=d.get("missing_fields", []),
            last_tool_result=d.get("last_tool_result"),
        )

    def __repr__(self) -> str:
        """String representation of the state."""
        return f"AgentState(status={self.status}, messages={len(self.messages)}, missing_fields={self.missing_fields}, last_tool_result={self.last_tool_result})"

    def __eq__(self, other: Any) -> bool:
        """Compare two states for equality."""
        if not isinstance(other, AgentState):
            return False
        return (
            self.status == other.status and
            self.messages == other.messages and
            self.missing_fields == other.missing_fields and
            self.last_tool_result == other.last_tool_result
        ) 