import os
import sys
import json
import logging
import asyncio
import ast
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, TypedDict, Annotated, Sequence, Union
from pydantic.v1 import BaseModel, Field
from dotenv import load_dotenv
from langchain.agents import create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from backend.state_manager import StateManager
from backend.google_services.calendar import GoogleCalendarService
from backend.google_services.gmail import GoogleGmailService
from backend.google_services.fit import GoogleFitnessService
from backend.google_services.tasks import GoogleTasksService
from backend.google_services.drive import GoogleDriveService
from backend.google_services.sheets import GoogleSheetsService
from backend.google_services.maps import GoogleMapsService
from langchain.agents import AgentExecutor
from langchain.agents import ZeroShotAgent
from langchain.chains import LLMChain
import pytz

load_dotenv()
logger = logging.getLogger(__name__)

# Global conversation history (ephemeral, lost on restart)
GLOBAL_CONVERSATION_HISTORY = []

# Define the system prompt for the agent
SYSTEM_PROMPT = """You are a personal trainer AI assistant. Your goal is to help users achieve their fitness goals by:
1. Understanding their fitness goals and current level
2. Creating personalized workout plans
3. Tracking their progress
4. Providing motivation and guidance
5. Adjusting plans based on feedback and progress

You have access to various tools to help manage the user's fitness journey:
- Calendar: Schedule workouts and track availability
- Gmail: Send workout plans and progress updates
- Tasks: Create and manage workout-related tasks
- Drive: Store and organize workout plans and progress reports
- Sheets: Track workout data and progress metrics
- Maps: Find nearby gyms and workout locations

IMPORTANT CALENDAR CONFLICT HANDLING:
When creating calendar events, if you receive a "CONFLICT_DETECTED" response:
1. Present the conflicting events to the user
2. Ask them how they'd like to proceed:
   - "skip": Don't create the new event
   - "replace": Delete all conflicting events and create the new one
   - "delete": Delete the first conflicting event and create the new one
3. Use the resolve_calendar_conflict tool with their choice

Always be professional, encouraging, and focused on helping the user achieve their fitness goals."""

class FindNearbyWorkoutLocationsInput(BaseModel):
    lat: float = Field(..., description="Latitude of the location")
    lng: float = Field(..., description="Longitude of the location")
    radius: int = Field(5000, description="Search radius in meters (default 5000)")

class PersonalTrainerAgent:
    """
    An AI-powered personal trainer agent that integrates with various Google services
    to provide personalized workout recommendations and tracking.
    """
    def __init__(
        self,
        calendar_service: GoogleCalendarService,
        gmail_service: GoogleGmailService,
        tasks_service: GoogleTasksService,
        drive_service: GoogleDriveService,
        sheets_service: GoogleSheetsService,
        maps_service: Optional[GoogleMapsService] = None
    ):
        """Initialize the personal trainer agent."""
        self.calendar_service = calendar_service
        self.gmail_service = gmail_service
        self.tasks_service = tasks_service
        self.drive_service = drive_service
        self.sheets_service = sheets_service
        self.maps_service = maps_service
        
        # Initialize the LLM
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0.7,
            streaming=True
        )
        
        # Initialize the tools
        self.tools = [
            Tool(
                name="get_calendar_events",
                func=self.calendar_service.get_upcoming_events,
                description="Get upcoming calendar events"
            ),
            Tool(
                name="create_calendar_event",
                func=self.calendar_service.write_event,
                description="Create a new calendar event"
            ),
            Tool(
                name="resolve_calendar_conflict",
                func=self._resolve_calendar_conflict,
                description="Resolve calendar conflicts by replacing, deleting, or skipping conflicting events"
            ),
            Tool(
                name="delete_events_in_range",
                func=self.calendar_service.delete_events_in_range,
                description="Delete all calendar events within a specified time range"
            ),
            Tool(
                name="send_email",
                func=self.gmail_service.send_message,
                description="Send an email"
            ),
            Tool(
                name="create_task",
                func=self.tasks_service.create_task,
                description="Create a new task"
            ),
            Tool(
                name="get_tasks",
                func=self.tasks_service.get_tasks,
                description="Get tasks"
            ),
            Tool(
                name="search_drive",
                func=self.drive_service.list_files,
                description="Search Google Drive files"
            ),
            Tool(
                name="get_sheet_data",
                func=self.sheets_service.get_sheet_data,
                description="Get data from a Google Sheet"
            )
        ]
        
        # Add maps tools only if maps_service is provided
        if self.maps_service:
            self.tools.extend([
                Tool(
                    name="get_directions",
                    func=self.maps_service.get_directions,
                    description="Get directions between two locations"
                ),
                Tool(
                    name="find_nearby_workout_locations",
                    func=self.maps_service.find_nearby_workout_locations,
                    description="Find nearby workout locations (gyms, fitness centers, etc.) near a given location"
                )
            ])
        
    async def async_init(self):
        """Initialize the agent asynchronously."""
        print("Initializing agent...")
        # Initialize the agent with the custom workflow
        self.agent = await self._create_agent_workflow()
        print(f"Agent initialized with {len(self.tools)} tools:")
        for tool in self.tools:
            print(f"- {tool.name}: {tool.description}")
        print("Agent initialization complete.")

    async def _create_agent_workflow(self):
        """Create a simple custom agent that directly uses the LLM and tools."""
        # We'll create a simple agent that just returns the LLM itself
        # The custom logic will be handled in decide_next_action
        return self.llm

    def _format_tool_response(self, tool_name: str, tool_input: str) -> str:
        """Format a tool response in a user-friendly way."""
        tool_responses = {
            "get_calendar_events": f"I'll check your calendar for {tool_input}.",
            "create_calendar_event": "I'll schedule that workout for you.",
            "send_email": "I'll send that email for you.",
            "create_task": "I'll create that task for you.",
            "get_tasks": f"I'll check your tasks for {tool_input}.",
            "search_drive": f"I'll search your Drive for {tool_input}.",
            "get_sheet_data": "I'll get that data from your spreadsheet.",
            "get_directions": "I'll get directions for you.",
            "find_nearby_workout_locations": "I'll find nearby workout locations for you."
        }
        return tool_responses.get(tool_name, "I'll help you with that.")

    async def decide_next_action(self, history):
        """Decide the next action based on the conversation history."""
        try:
            # Convert history to the format expected by the agent
            if isinstance(history, list):
                # Get the last message's content
                last_message = history[-1]
                if hasattr(last_message, 'content'):
                    input_text = last_message.content
                else:
                    input_text = str(last_message)
                # Get previous messages for chat history
                chat_history = []
                for msg in history[:-1]:
                    if hasattr(msg, 'content'):
                        chat_history.append(msg.content)
                    else:
                        chat_history.append(str(msg))
            else:
                input_text = str(history)
                chat_history = []

            # Create the system prompt with tool descriptions
            tool_descriptions = []
            for tool in self.tools:
                tool_descriptions.append(f"- {tool.name}: {tool.description}")
            
            system_prompt = f"""You are a personal trainer AI assistant. Your goal is to help users achieve their fitness goals.

You have access to the following tools:
{chr(10).join(tool_descriptions)}

When a user asks for something that requires using a tool, respond with:
TOOL_CALL: <tool_name> <tool_arguments>

For example:
- If they ask to check their calendar: TOOL_CALL: get_calendar_events ""
- If they ask to create a workout: TOOL_CALL: create_calendar_event "Workout session at 6 PM tomorrow"
- If they ask to send an email: TOOL_CALL: send_email "recipient@example.com|Subject|Message content"
- If they ask to delete events in a time range: TOOL_CALL: delete_events_in_range "2024-03-20T00:00:00Z|2024-03-21T00:00:00Z"
  Note: The time range should be in ISO format with UTC timezone (Z suffix), separated by a pipe character (|)

IMPORTANT:
- The most recent message in the conversation history is the user's current request and should be prioritized when deciding how to respond or which tool to call.
- Use the timestamps in the conversation history to understand the order and recency of messages, but always focus on the latest message for the user's intent.
- Use the rest of the conversation history for context, but do not let older messages override the user's most recent request.

IMPORTANT CALENDAR CONFLICT HANDLING:
When creating calendar events, if you receive a "CONFLICT_DETECTED" response:
1. Present the conflicting events to the user
2. Ask them how they'd like to proceed:
   - "skip": Don't create the new event
   - "replace": Delete all conflicting events and create the new one
   - "delete": Delete the first conflicting event and create the new one
3. Use the resolve_calendar_conflict tool with their choice: TOOL_CALL: resolve_calendar_conflict '{{"event_details": {{...}}, "action": "skip"}}'

If they don't need a tool, just respond normally with helpful, encouraging fitness advice.

Always be professional, encouraging, and focused on helping the user achieve their fitness goals."""

            # Prepare the messages for the LLM
            messages = [SystemMessage(content=system_prompt)]
            
            # Add chat history
            for msg in chat_history:
                messages.append(HumanMessage(content=msg))
            
            # Add the current message
            messages.append(HumanMessage(content=input_text))

            print(f"Agent input: {input_text}")
            response = await self.agent.ainvoke(messages)
            print(f"Agent response type: {type(response)}")
            print(f"Agent response: {response}")
            
            # Check if the response contains a tool call
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            if "TOOL_CALL:" in response_content:
                # Parse the tool call
                tool_call_line = response_content.split("TOOL_CALL:")[1].strip().split("\n")[0]
                parts = tool_call_line.split(" ", 1)
                if len(parts) >= 2:
                    tool_name = parts[0].strip()
                    tool_args = parts[1].strip()
                    
                    return {
                        "type": "tool_call",
                        "tool": tool_name,
                        "args": tool_args
                    }
            
            # Handle regular messages
            return {
                "type": "message",
                "content": response_content
            }
        except Exception as e:
            print(f"Error in decide_next_action: {e}")
            import traceback
            traceback.print_exc()
            return {
                "type": "message",
                "content": "I apologize, but I encountered an error. Please try again."
            }

    async def process_tool_result(self, history):
        """Process the tool result and decide the next action."""
        response = await self.agent.ainvoke({
            "input": history,
            "intermediate_steps": []
        })
        print(f"Agent response in process_tool_result: {response}")
        if hasattr(response, "return_values"):
            output = response.return_values["output"]
            if isinstance(output, AIMessage) and hasattr(output, "additional_kwargs"):
                function_call = output.additional_kwargs.get("function_call", {})
                if function_call:
                    tool_name = function_call.get("name", "")
                    tool_input = function_call.get("arguments", "{}")
                    tool_result = await self._execute_tool(tool_name, tool_input)
                    history.append(tool_result)
                    # Feed the tool result back to the agent to generate a user-facing message
                    return await self.process_tool_result(history)
            if isinstance(output, AIMessage) and hasattr(output, "content"):
                return {
                    "type": "message",
                    "content": output.content
                }
            elif isinstance(output, str):
                return {
                    "type": "message",
                    "content": output
                }
        elif isinstance(response, str):
            return {
                "type": "message",
                "content": response
            }
        return {
            "type": "done"
        }

    async def _summarize_tool_result(self, tool_name, tool_result):
        """Prompt the LLM to summarize the tool result in natural language."""
        summary_prompt = f"Summarize the following tool result for the user in clear, natural language. Be concise, friendly, and helpful.\n\nTOOL RESULT: {tool_result}"
        messages = [
            SystemMessage(content="You are a helpful assistant. Always respond in clear, natural language, never as a code block or raw data."),
            HumanMessage(content=summary_prompt)
        ]
        try:
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
        except Exception as e:
            logger.error(f"LLM failed to summarize tool result: {e}")
            return None

    async def agent_conversation_loop(self, user_input):
        """Loop-based orchestration to support multi-step agent actions with enforced tool result summarization."""
        state = "AGENT_THINKING"
        history = [user_input]
        responses = []
        agent_action = None
        tool_result = None
        last_tool = None

        while state != "DONE":
            print(f"Current state: {state}")
            if state == "AGENT_THINKING":
                agent_action = await self.decide_next_action(history)
                print(f"Agent action: {agent_action}")
                if agent_action["type"] == "message":
                    responses.append(agent_action["content"])
                    state = "DONE"
                elif agent_action["type"] == "tool_call":
                    last_tool = agent_action["tool"]
                    print(f"About to call tool: {last_tool} with args: {agent_action['args']}")
                    # Send confirmation message before calling tool
                    confirmation_message = await self._get_tool_confirmation_message(last_tool, agent_action["args"])
                    responses.append(confirmation_message)
                    state = "AGENT_TOOL_CALL"
                else:
                    state = "DONE"
            elif state == "AGENT_TOOL_CALL":
                tool_result = await self._execute_tool(agent_action["tool"], agent_action["args"])
                print(f"Tool result for {last_tool}: {tool_result}")
                # Add the tool result as a message in the history
                history.append(AIMessage(content=f"TOOL RESULT: {tool_result}"))
                # Always go to summarize state after a tool call
                state = "AGENT_SUMMARIZE_TOOL_RESULT"
            elif state == "AGENT_SUMMARIZE_TOOL_RESULT":
                # Always require the LLM to summarize the tool result for the user
                summary = await self._summarize_tool_result(last_tool, tool_result)
                if summary:
                    responses.append(summary)
                    state = "DONE"
                else:
                    # If agent does not summarize, provide a default summary based on the tool
                    print(f"Using default summary for tool: {last_tool}")
                    if last_tool == "get_calendar_events":
                        responses.append(f"Here are your upcoming workouts: {tool_result}")
                    elif last_tool == "get_directions":
                        responses.append(f"Here are the directions to your workout location: {tool_result}")
                    elif last_tool == "create_calendar_event":
                        responses.append("Your workout has been scheduled in your calendar!")
                    else:
                        responses.append(f"I've completed your request. Here's what I found: {tool_result}")
                    state = "DONE"

        # Final fallback: if responses is empty but we have a tool_result and last_tool, return the default summary
        if not responses and tool_result and last_tool:
            print(f"Final fallback triggered. last_tool: {last_tool}, tool_result: {tool_result}")
            if last_tool == "get_calendar_events":
                responses.append(f"Here are your upcoming workouts: {tool_result}")
            elif last_tool == "get_directions":
                responses.append(f"Here are the directions to your workout location: {tool_result}")
            elif last_tool == "create_calendar_event":
                responses.append("Your workout has been scheduled in your calendar!")
            else:
                responses.append(f"I've completed your request. Here's what I found: {tool_result}")

        print(f"Final responses: {responses}")
        return responses

    async def _get_tool_confirmation_message(self, tool_name: str, tool_args: str) -> str:
        """Generate a user-friendly confirmation message before calling a tool. For create_calendar_event, use the LLM to make it natural."""
        if tool_name == "create_calendar_event":
            try:
                prompt = f"""
Rephrase the following workout event description into a natural, concise message indicating that you are processing the request, as if you are their personal trainer assistant. Example: 'I'll schedule your 10am workout session in your calendar for tomorrow.'

Event description: {tool_args}

Confirmation message:"""
                messages = [
                    SystemMessage(content="You are a helpful assistant that writes natural, concise messages indicating that you are processing a request. Never indicate that the action is already completed."),
                    HumanMessage(content=prompt)
                ]
                response = await self.llm.ainvoke(messages)
                return response.content.strip()
            except Exception as e:
                logger.error(f"LLM failed to generate confirmation message: {e}")
                return f"I'll schedule your workout: {tool_args}"
        tool_messages = {
            "get_calendar_events": "I'll check your calendar for upcoming events.",
            "resolve_calendar_conflict": "I'll resolve the calendar conflict as requested.",
            "send_email": "I'll send that email for you.",
            "create_task": f"I'll create a task for you: {tool_args}",
            "get_tasks": "I'll check your tasks.",
            "search_drive": f"I'll search your Drive for: {tool_args}",
            "get_sheet_data": "I'll get that data from your spreadsheet.",
            "get_directions": f"I'll get directions for you: {tool_args}",
            "find_nearby_workout_locations": f"I'll find nearby workout locations: {tool_args}"
        }
        return tool_messages.get(tool_name, f"I'll help you with that using {tool_name}.")

    async def process_messages(self, messages):
        """Process a list of messages and return a response. Uses global conversation history for context, returns only the latest response as a string."""
        if not self.agent:
            raise RuntimeError("Agent not initialized. Call async_init() first.")

        # Append new messages to the global conversation history with timestamps
        for msg in messages:
            if isinstance(msg, dict):
                msg = msg.copy()
                msg["timestamp"] = datetime.utcnow().isoformat() + "Z"
            GLOBAL_CONVERSATION_HISTORY.append(msg)

        # Use the full conversation history for context
        input_messages = []
        for msg in GLOBAL_CONVERSATION_HISTORY:
            if isinstance(msg, dict):
                timestamp = msg.get("timestamp", "")
                role = msg.get("role", "user")
                content = msg.get("content", "")
                content_with_time = f"[{timestamp}] {content}" if timestamp else content
                if role == "user":
                    input_messages.append(HumanMessage(content=content_with_time))
                elif role == "assistant":
                    input_messages.append(AIMessage(content=content_with_time))
                elif role == "system":
                    input_messages.append(SystemMessage(content=content_with_time))
            else:
                input_messages.append(msg)

        # Use the new agent_conversation_loop for multi-step orchestration
        responses = await self.agent_conversation_loop(input_messages)
        # Always return only the latest response as a string
        if isinstance(responses, list):
            return responses[-1] if responses else "No response generated"
        return responses

    async def process_messages_stream(self, messages):
        """Process a list of messages and yield responses as they become available. Uses global conversation history for context."""
        if not self.agent:
            raise RuntimeError("Agent not initialized. Call async_init() first.")

        # Append new messages to the global conversation history with timestamps
        for msg in messages:
            if isinstance(msg, dict):
                msg = msg.copy()
                msg["timestamp"] = datetime.utcnow().isoformat() + "Z"
            GLOBAL_CONVERSATION_HISTORY.append(msg)

        # Use the full conversation history for context
        input_messages = []
        for msg in GLOBAL_CONVERSATION_HISTORY:
            if isinstance(msg, dict):
                timestamp = msg.get("timestamp", "")
                role = msg.get("role", "user")
                content = msg.get("content", "")
                content_with_time = f"[{timestamp}] {content}" if timestamp else content
                if role == "user":
                    input_messages.append(HumanMessage(content=content_with_time))
                elif role == "assistant":
                    input_messages.append(AIMessage(content=content_with_time))
                elif role == "system":
                    input_messages.append(SystemMessage(content=content_with_time))
            else:
                input_messages.append(msg)

        # Use the new streaming agent_conversation_loop for real-time responses
        async for response in self.agent_conversation_loop_stream(input_messages):
            yield response

    async def agent_conversation_loop_stream(self, user_input):
        """Streaming version of the conversation loop that yields responses as they become available."""
        state = "AGENT_THINKING"
        history = [user_input]
        agent_action = None
        tool_result = None
        last_tool = None

        while state != "DONE":
            print(f"Current state: {state}")
            if state == "AGENT_THINKING":
                agent_action = await self.decide_next_action(history)
                print(f"Agent action: {agent_action}")
                if agent_action["type"] == "message":
                    yield agent_action["content"]
                    state = "DONE"
                elif agent_action["type"] == "tool_call":
                    last_tool = agent_action["tool"]
                    print(f"About to call tool: {last_tool} with args: {agent_action['args']}")
                    # Send confirmation message before calling tool
                    confirmation_message = await self._get_tool_confirmation_message(last_tool, agent_action["args"])
                    yield confirmation_message
                    state = "AGENT_TOOL_CALL"
                else:
                    state = "DONE"
            elif state == "AGENT_TOOL_CALL":
                tool_result = await self._execute_tool(agent_action["tool"], agent_action["args"])
                print(f"Tool result for {last_tool}: {tool_result}")
                # Add the tool result as a message in the history
                history.append(AIMessage(content=f"TOOL RESULT: {tool_result}"))
                # Always go to summarize state after a tool call
                state = "AGENT_SUMMARIZE_TOOL_RESULT"
            elif state == "AGENT_SUMMARIZE_TOOL_RESULT":
                # Always require the LLM to summarize the tool result for the user
                summary = await self._summarize_tool_result(last_tool, tool_result)
                if summary:
                    yield summary
                    state = "DONE"
                else:
                    # If agent does not summarize, provide a default summary based on the tool
                    print(f"Using default summary for tool: {last_tool}")
                    if last_tool == "get_calendar_events":
                        yield f"Here are your upcoming workouts: {tool_result}"
                    elif last_tool == "get_directions":
                        yield f"Here are the directions to your workout location: {tool_result}"
                    elif last_tool == "create_calendar_event":
                        yield "Your workout has been scheduled in your calendar!"
                    else:
                        yield f"I've completed your request. Here's what I found: {tool_result}"
                    state = "DONE"

        # Final fallback: if we have a tool_result and last_tool but no responses yielded
        if tool_result and last_tool:
            print(f"Final fallback triggered. last_tool: {last_tool}, tool_result: {tool_result}")
            if last_tool == "get_calendar_events":
                yield f"Here are your upcoming workouts: {tool_result}"
            elif last_tool == "get_directions":
                yield f"Here are the directions to your workout location: {tool_result}"
            elif last_tool == "create_calendar_event":
                yield "Your workout has been scheduled in your calendar!"
            else:
                yield f"I've completed your request. Here's what I found: {tool_result}"

    def _parse_tool_string(self, output_str):
        """Parse tool name and input from a raw tool invocation string."""
        tool_start = output_str.find("tool='") + 6
        tool_end = output_str.find("'", tool_start)
        tool_name = output_str[tool_start:tool_end]
        input_start = output_str.find("tool_input='") + 11
        input_end = output_str.find("'", input_start)
        tool_input = output_str[input_start:input_end]
        return tool_name, tool_input

    async def _convert_natural_language_to_calendar_json(self, natural_language_input: str) -> str:
        """Convert natural language input to JSON format for calendar events using LLM."""
        try:
            # Get current date/time information
            now = datetime.now()
            current_year = now.year
            current_month = now.month
            current_day = now.day
            tomorrow = now + timedelta(days=1)
            tomorrow_str = tomorrow.strftime("%Y-%m-%d")
            
            # Create a prompt to convert natural language to JSON
            conversion_prompt = f"""Convert the following natural language description into a JSON object for creating a calendar event.

Natural language input: "{natural_language_input}"

Current date context:
- Today is {now.strftime('%Y-%m-%d')} ({now.strftime('%A')})
- Tomorrow is {tomorrow_str} ({tomorrow.strftime('%A')})
- Current time is {now.strftime('%H:%M')}

Requirements:
- summary: A short, descriptive title for the event
- start: Start time in ISO format (YYYY-MM-DDTHH:MM:SS) - use current year ({current_year})
- end: End time in ISO format (YYYY-MM-DDTHH:MM:SS) - typically 1 hour after start unless specified
- description: A brief description of the event (optional)
- location: Location of the event (optional)

Rules:
- If no specific time is mentioned, default to 6:00 PM tomorrow
- If no duration is mentioned, default to 1 hour
- Use tomorrow's date if "tomorrow" is mentioned
- Use today's date if "today" is mentioned
- For workout events, use appropriate fitness-related descriptions
- Always use the current year ({current_year}) unless a specific year is mentioned
- Use 24-hour format for times

Return ONLY the JSON object, no additional text or explanation.

Example output:
{{"summary": "Workout Session", "start": "{tomorrow_str}T18:00:00", "end": "{tomorrow_str}T19:00:00", "description": "Fitness workout session", "location": "Gym"}}"""

            # Use the LLM to convert the input
            messages = [
                SystemMessage(content="You are a helpful assistant that converts natural language to JSON format for calendar events. Always return valid JSON only."),
                HumanMessage(content=conversion_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            json_string = response.content.strip()
            
            # Validate that the response is valid JSON
            try:
                json.loads(json_string)
                return json_string
            except json.JSONDecodeError:
                # If the response isn't valid JSON, try to extract JSON from it
                import re
                json_match = re.search(r'\{.*\}', json_string, re.DOTALL)
                if json_match:
                    extracted_json = json_match.group(0)
                    json.loads(extracted_json)  # Validate
                    return extracted_json
                else:
                    raise ValueError("LLM response is not valid JSON")
                    
        except Exception as e:
            logger.error(f"Error converting natural language to JSON: {e}")
            # Return a fallback JSON with default values using actual current date
            tomorrow = datetime.now() + timedelta(days=1)
            tomorrow_str = tomorrow.strftime("%Y-%m-%d")
            return json.dumps({
                "summary": "Workout Session",
                "start": f"{tomorrow_str}T18:00:00",
                "end": f"{tomorrow_str}T19:00:00",
                "description": "Fitness workout session",
                "location": "Gym"
            })

    async def _execute_tool(self, tool_name, tool_input):
        """Execute a tool with the given input."""
        try:
            # Convert tool_input to dict if needed for create_calendar_event
            if tool_name == "create_calendar_event" and isinstance(tool_input, str):
                try:
                    # Use the LLM to convert natural language to event dict (returns JSON string)
                    tool_input = await self._convert_natural_language_to_calendar_json(tool_input)
                    # Parse the JSON string to a Python dict
                    tool_input = json.loads(tool_input)
                    # Ensure start and end are RFC3339 (with timezone)
                    for time_field in ["start", "end"]:
                        if time_field in tool_input and isinstance(tool_input[time_field], str):
                            # If no timezone info, append 'Z' for UTC
                            if "T" in tool_input[time_field] and not (tool_input[time_field].endswith("Z") or "+" in tool_input[time_field]):
                                tool_input[time_field] += "Z"
                            # Wrap as dict for Google Calendar API
                            tool_input[time_field] = {"dateTime": tool_input[time_field], "timeZone": "UTC"}
                except Exception as e:
                    logger.error(f"Failed to convert event description: {e}")
                    raise
            if tool_name == "get_calendar_events":
                return await self.calendar_service.get_upcoming_events(tool_input)
            elif tool_name == "create_calendar_event":
                return await self.calendar_service.write_event(tool_input)
            elif tool_name == "resolve_calendar_conflict":
                return await self._resolve_calendar_conflict(tool_input)
            elif tool_name == "delete_events_in_range":
                # Parse the time range string (format: "start_time|end_time")
                if isinstance(tool_input, str):
                    # Remove any extra quotes from the input
                    tool_input = tool_input.strip('"')
                    start_time, end_time = tool_input.split('|')
                    return await self.calendar_service.delete_events_in_range(start_time, end_time)
                else:
                    # Handle dictionary input
                    start_time = tool_input.get('start_time')
                    end_time = tool_input.get('end_time')
                    if not start_time or not end_time:
                        raise ValueError("Both start_time and end_time are required")
                    return await self.calendar_service.delete_events_in_range(start_time, end_time)
            elif tool_name == "send_email":
                return await self.gmail_service.send_message(tool_input)
            elif tool_name == "create_task":
                return await self.tasks_service.create_task(tool_input)
            elif tool_name == "get_tasks":
                return await self.tasks_service.get_tasks(tool_input)
            elif tool_name == "search_drive":
                return await self.drive_service.list_files(tool_input)
            elif tool_name == "get_sheet_data":
                return await self.sheets_service.get_sheet_data(tool_input)
            elif tool_name == "get_directions" and self.maps_service:
                return await self.maps_service.get_directions(tool_input)
            elif tool_name == "find_nearby_workout_locations" and self.maps_service:
                return await self.maps_service.find_nearby_workout_locations(tool_input)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            raise

    def _create_tools(self):
        """Create the tools for the agent."""
        tools = []
        if self.calendar_service:
            logger.debug("Adding Calendar tools...")
            tools.extend([
                Tool(
                    name="get_calendar_events",
                    func=self.calendar_service.get_upcoming_events,
                    description="Get upcoming calendar events"
                ),
                Tool(
                    name="create_calendar_event",
                    func=self.calendar_service.write_event,
                    description="Create a new calendar event"
                )
            ])
        if self.gmail_service:
            logger.debug("Adding Gmail tools...")
            tools.extend([
                Tool(
                    name="send_email",
                    func=self.gmail_service.send_message,
                    description="Send an email to a recipient"
                )
            ])
        if self.tasks_service:
            logger.debug("Adding Tasks tools...")
            tools.extend([
                Tool(
                    name="create_task",
                    func=self.tasks_service.create_task,
                    description="Create a new task"
                ),
                Tool(
                    name="get_tasks",
                    func=self.tasks_service.get_tasks,
                    description="Get tasks from the task list"
                )
            ])
        if self.drive_service:
            logger.debug("Adding Drive tools...")
            tools.extend([
                Tool(
                    name="search_drive",
                    func=self.drive_service.list_files,
                    description="Search for files in Google Drive"
                )
            ])
        if self.sheets_service:
            logger.debug("Adding Sheets tools...")
            tools.extend([
                Tool(
                    name="get_sheet_data",
                    func=self.sheets_service.get_sheet_data,
                    description="Get data from a Google Sheet"
                )
            ])
        if self.maps_service:
            logger.debug("Adding Maps tools...")
            tools.extend([
                Tool(
                    name="get_directions",
                    func=self.maps_service.get_directions,
                    description="Get directions between two locations"
                ),
                Tool(
                    name="find_nearby_workout_locations",
                    func=self.maps_service.find_nearby_workout_locations,
                    description="Find nearby workout locations (gyms, fitness centers, etc.) near a given location"
                )
            ])
        logger.info(f"Created {len(tools)} tools for agent")
        return tools

    async def _handle_calendar_operations(self, operation_json):
        """Handle all calendar operations through a single method."""
        logger.info(f"[GoogleCalendar] Received operation: {operation_json}")
        # Parse operation JSON
        if not isinstance(operation_json, dict):
            try:
                operation_json = json.loads(operation_json)
            except Exception as e:
                logger.error(f"[GoogleCalendar] Could not parse operation_json: {e}")
                return "Error: Invalid operation format"
        action = operation_json.get("action")
        if not action:
            return "Error: Missing 'action' in calendar operation"
        try:
            if action == "getUpcoming":
                max_results = operation_json.get("maxResults", 10)
                return await self.calendar_service.get_upcoming_events(max_results)
            elif action == "getForDate":
                date = operation_json.get("date")
                if not date:
                    return "Error: Missing 'date' for getForDate operation"
                return await self.calendar_service.get_events_for_date(date)
            elif action == "create":
                event_details = {
                    "summary": operation_json.get("summary", "Workout"),
                    "start": operation_json.get("start"),
                    "end": operation_json.get("end"),
                    "description": operation_json.get("description", "General fitness workout."),
                    "location": operation_json.get("location", "Gym")
                }
                # Convert to proper calendar format
                event_details = self._convert_to_calendar_format(event_details)
                return await self.calendar_service.write_event(event_details)
            elif action == "delete":
                event_id = operation_json.get("eventId")
                if not event_id:
                    return "Error: Missing 'eventId' for delete operation"
                return await self.calendar_service.delete_event(event_id)
            else:
                return f"Error: Unknown calendar action '{action}'"
        except Exception as e:
            logger.error(f"[GoogleCalendar] Error handling operation: {e}")
            return f"Error: {str(e)}"

    def _convert_message(self, msg):
        """Convert a message dict to a LangChain message object, with robust logging and error handling."""
        logger.debug(f"_convert_message called with: {msg}")
        print(f"[DEBUG] _convert_message called with: {msg}")
        if not isinstance(msg, dict):
            logger.warning(f"Message is not a dict: {msg}")
            print(f"[WARN] Message is not a dict: {msg}")
            return None
        role = msg.get("role", "user").lower()  # Normalize role to lowercase
        content = msg.get("content", "")
        # Validate content
        if not content or not isinstance(content, str):
            logger.warning(f"Message has invalid content: {msg}")
            print(f"[WARN] Message has invalid content: {msg}")
            return None
        content = content.strip()
        if not content:
            logger.warning(f"Message has empty content after stripping: {msg}")
            print(f"[WARN] Message has empty content after stripping: {msg}")
            return None
        # Convert to appropriate message type
        try:
            if role == "user":
                logger.debug(f"Returning HumanMessage for: {content}")
                print(f"[DEBUG] Returning HumanMessage for: {content}")
                return HumanMessage(content=content)
            elif role == "assistant":
                logger.debug(f"Returning AIMessage for: {content}")
                print(f"[DEBUG] Returning AIMessage for: {content}")
                return AIMessage(content=content)
            elif role == "system":
                logger.debug(f"Returning SystemMessage for: {content}")
                print(f"[DEBUG] Returning SystemMessage for: {content}")
                return SystemMessage(content=content)
            else:
                logger.warning(f"Unknown role '{role}', defaulting to HumanMessage: {msg}")
                print(f"[WARN] Unknown role '{role}', defaulting to HumanMessage: {msg}")
                return HumanMessage(content=content)
        except Exception as e:
            logger.error(f"Error converting message: {e}")
            print(f"[ERROR] Error converting message: {e}")
            return None

    def _get_tomorrow_date(self):
        """Get tomorrow's date in ISO format."""
        tomorrow = datetime.now() + timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d")

    def _convert_to_calendar_format(self, event_details):
        """Convert event details to Google Calendar format."""
        converted = event_details.copy()
        
        # Get user timezone (default to Pacific Time)
        user_tz = pytz.timezone('America/Los_Angeles')
        
        # Convert start time if it's a string
        if 'start' in converted and isinstance(converted['start'], str):
            # Parse the datetime string and add timezone
            try:
                dt = datetime.fromisoformat(converted['start'].replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = user_tz.localize(dt)
                converted['start'] = {'dateTime': dt.isoformat()}
            except ValueError:
                # If parsing fails, try to add timezone to the string
                if not converted['start'].endswith('Z') and '+' not in converted['start']:
                    converted['start'] = {'dateTime': converted['start'] + '-08:00'}  # PST
                else:
                    converted['start'] = {'dateTime': converted['start']}
        
        # Convert end time if it's a string
        if 'end' in converted and isinstance(converted['end'], str):
            # Parse the datetime string and add timezone
            try:
                dt = datetime.fromisoformat(converted['end'].replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = user_tz.localize(dt)
                converted['end'] = {'dateTime': dt.isoformat()}
            except ValueError:
                # If parsing fails, try to add timezone to the string
                if not converted['end'].endswith('Z') and '+' not in converted['end']:
                    converted['end'] = {'dateTime': converted['end'] + '-08:00'}  # PST
                else:
                    converted['end'] = {'dateTime': converted['end']}
        
        return converted

    async def _resolve_calendar_conflict(self, conflict_data):
        """Handle calendar conflict resolution."""
        try:
            if isinstance(conflict_data, str):
                conflict_data = json.loads(conflict_data)
            
            event_details = conflict_data.get("event_details")
            conflict_action = conflict_data.get("action", "skip")  # skip, replace, or delete
            
            if not event_details:
                return "Error: Missing event_details in conflict resolution request"
            
            # Convert to proper format if needed
            if isinstance(event_details, str):
                event_details = json.loads(event_details)
            
            event_details = self._convert_to_calendar_format(event_details)
            result = await self.calendar_service.write_event_with_conflict_resolution(event_details, conflict_action)
            
            if isinstance(result, dict) and result.get("type") == "conflict":
                return f"Conflict still exists after resolution attempt: {result['message']}"
            else:
                return f"Successfully created event with conflict resolution (action: {conflict_action})"
                
        except Exception as e:
            logger.error(f"Error resolving calendar conflict: {e}")
            return f"Error resolving conflict: {str(e)}"

def clear_global_conversation_history():
    """Utility function to clear the global conversation history (for tests)."""
    GLOBAL_CONVERSATION_HISTORY.clear()
