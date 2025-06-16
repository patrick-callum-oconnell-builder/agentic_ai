import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated
import re
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI
from langgraph.graph import StateGraph, END
from backend.agent_state import AgentState
from backend.google_services.maps import GoogleMapsService
from backend.prompts import AGENT_CONTEXT_PROMPT

load_dotenv()
logger = logging.getLogger(__name__)

class Message(TypedDict):
    role: str
    content: str

class PersonalTrainerAgent:
    """
    Personal Trainer Agent using LangGraph for orchestration.
    """
    def __init__(self, maps_service: GoogleMapsService):
        self.maps_service = maps_service
        self.client = AsyncOpenAI()
        self.graph = self._create_graph()

    @classmethod
    async def ainit(cls, maps_service: GoogleMapsService) -> "PersonalTrainerAgent":
        agent = cls(maps_service)
        return agent

    def _parse_tool_call(self, content: str):
        # Try to parse JSON format
        try:
            json_match = re.search(r'```(?:json)?\s*({[^}]+})\s*```', content)
            if json_match:
                tool_call = json.loads(json_match.group(1))
                if isinstance(tool_call, dict) and "tool_name" in tool_call and "tool_args" in tool_call:
                    return tool_call["tool_name"], tool_call["tool_args"]
        except Exception:
            pass
        # Try to parse natural language format
        try:
            tool_match = re.search(r'(?:use|call|invoke|execute)\s+(\w+)(?:\s+with\s+args?)?\s*[:=]?\s*({[^}]+})', content, re.IGNORECASE)
            if tool_match:
                tool_name = tool_match.group(1)
                tool_args = json.loads(tool_match.group(2))
                return tool_name, tool_args
        except Exception:
            pass
        return None, None

    def _create_graph(self):
        async def llm_node(state: AgentState) -> AgentState:
            messages = [
                {"role": "system", "content": AGENT_CONTEXT_PROMPT},
                *[{"role": m["role"], "content": m["content"]} for m in state.messages]
            ]
            
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=messages,
                temperature=0.7,
                stream=True
            )
            
            collected_content = []
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    collected_content.append(chunk.choices[0].delta.content)
            
            content = "".join(collected_content)
            state.messages.append({"role": "assistant", "content": content})
            return state

        async def tool_node(state: AgentState) -> AgentState:
            last_message = state.messages[-1]
            tool_name, tool_args = self._parse_tool_call(last_message["content"])
            if tool_name == "GoogleMaps" and tool_args:
                action = tool_args.get("action")
                if action == "find_workout_locations":
                    address = tool_args.get("address")
                    radius = tool_args.get("radius", 3218)
                    coords = await self.maps_service.geocode_address(address)
                    results = self.maps_service.find_nearby_workout_locations(coords, radius)
                    state.messages.append({"role": "assistant", "content": f"[TOOL RESULT]: {results}"})
                    return state
            state.messages.append({"role": "assistant", "content": "[TOOL RESULT]: Tool call failed or not recognized."})
            return state

        graph = StateGraph(AgentState)
        graph.add_node("llm", llm_node)
        graph.add_node("tool", tool_node)
        graph.add_edge("llm", "tool")
        graph.add_edge("tool", END)
        graph.set_entry_point("llm")
        return graph.compile()

    async def process_messages(self, messages: List[Message]) -> str:
        state = AgentState(messages=messages)
        result = await self.graph.ainvoke(state)
        # Return the last assistant message
        ai_messages = [m for m in result.messages if m["role"] == "assistant"]
        if ai_messages:
            last_message = ai_messages[-1]["content"]
            if "[TOOL RESULT]:" in last_message:
                return last_message.split("[TOOL RESULT]:", 1)[1].strip()
            return last_message
        return "I couldn't process your request. Please try again."

    async def tool_node(self, tool_call: dict) -> Any:
        # For direct tool node invocation in tests
        action = tool_call["tool_args"].get("action")
        if tool_call["tool_name"] == "GoogleMaps" and action == "find_workout_locations":
            address = tool_call["tool_args"].get("address")
            radius = tool_call["tool_args"].get("radius", 3218)
            coords = await self.maps_service.geocode_address(address)
            results = self.maps_service.find_nearby_workout_locations(coords, radius)
            return results
        return None
