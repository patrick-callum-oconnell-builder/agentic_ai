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
import dateparser
from datetime import timezone as dt_timezone

load_dotenv()
logger = logging.getLogger(__name__)

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

IMPORTANT CONVERSATION CONTEXT HANDLING:
1. Only use conversation history when:
   - The user explicitly refers to a previous conversation (e.g., "that workout we discussed")
   - The user uses pronouns like "it" or "that" that clearly refer to a previous topic
   - The user asks to modify or change something previously discussed
2. Treat as a new request when:
   - The user makes a direct request without referring to previous context
   - The user asks about a new topic or activity
   - The user's request is self-contained and doesn't need previous context
3. When a user confirms a specific time for a workout, ALWAYS use that exact time
4. Never override a previously confirmed time with a different time
5. If a user asks to change a time, only then should you propose a different time
6. If a user asks about a workout without specifying details and it's a new request, ask for the details rather than assuming previous context

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
        self.tools = []
        if self.calendar_service:
            self.tools.extend([
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
                )
            ])
        if self.gmail_service:
            self.tools.append(
                Tool(
                    name="send_email",
                    func=self.gmail_service.send_message,
                    description="Send an email"
                )
            )
        if self.tasks_service:
            self.tools.extend([
                Tool(
                    name="create_task",
                    func=self.tasks_service.create_task,
                    description="Create a new task"
                ),
                Tool(
                    name="get_tasks",
                    func=self.tasks_service.get_tasks,
                    description="Get tasks"
                )
            ])
        if self.drive_service:
            self.tools.append(
                Tool(
                    name="search_drive",
                    func=self.drive_service.list_files,
                    description="Search Google Drive files"
                )
            )
        if self.sheets_service:
            self.tools.append(
                Tool(
                    name="get_sheet_data",
                    func=self.sheets_service.get_sheet_data,
                    description="Get data from a Google Sheet"
                )
            )
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
            system_prompt = """You are a personal trainer AI assistant. Your goal is to help users achieve their fitness goals.

You have access to the following tools:
- get_calendar_events: Get upcoming calendar events
- create_calendar_event: Create a new calendar event
- resolve_calendar_conflict: Resolve calendar conflicts by replacing, deleting, or skipping conflicting events
- delete_events_in_range: Delete all calendar events within a specified time range
- send_email: Send an email
- create_task: Create a new task
- get_tasks: Get tasks
- search_drive: Search Google Drive files
- get_sheet_data: Get data from a Google Sheet
- get_directions: Get directions between two locations
- find_nearby_workout_locations: Find nearby workout locations (gyms, fitness centers, etc.) near a given location

When a user asks for something that requires using a tool, respond with:
TOOL_CALL: <tool_name> <tool_arguments>

For example:
- If they ask to check their calendar: TOOL_CALL: get_calendar_events ""
- If they ask to create a workout: TOOL_CALL: create_calendar_event "Workout session at 6 PM tomorrow"
- If they ask to send an email: TOOL_CALL: send_email "recipient@example.com|Subject|Message content"
- If they ask to delete events in a time range: TOOL_CALL: delete_events_in_range "2024-03-20T00:00:00Z|2024-03-21T00:00:00Z"
  Note: The time range should be in ISO format with UTC timezone (Z suffix), separated by a pipe character (|)

CRITICAL INSTRUCTION FOR HANDLING CONVERSATION CONTEXT:
1. Only use conversation history when:
   - The user explicitly refers to a previous conversation (e.g., "that workout we discussed")
   - The user uses pronouns like "it" or "that" that clearly refer to a previous topic
   - The user asks to modify or change something previously discussed

2. Treat as a new request when:
   - The user makes a direct request without referring to previous context
   - The user asks about a new topic or activity
   - The user's request is self-contained and doesn't need previous context

3. Calendar event rules:
   - When a user confirms a specific time for a workout, ALWAYS use that exact time
   - Never override a previously confirmed time with a different time
   - If a user asks to change a time, only then should you propose a different time
   - If a user asks about a workout without specifying details and it's a new request, ask for the details rather than assuming previous context

IMPORTANT CALENDAR CONFLICT HANDLING:
When creating calendar events, if you receive a "CONFLICT_DETECTED" response:
1. Present the conflicting events to the user
2. Ask them how they'd like to proceed:
   - "skip": Don't create the new event
   - "replace": Delete all conflicting events and create the new one
   - "delete": Delete the first conflicting event and create the new one
3. Use the resolve_calendar_conflict tool with their choice

If they don't need a tool, just respond normally with helpful, encouraging fitness advice.

Always be professional, encouraging, and focused on helping the user achieve their fitness goals."""

            # Create the prompt with the full conversation history
            prompt = f"{system_prompt}\n\nConversation history:\n"
            for msg in chat_history:
                prompt += f"{msg}\n"
            prompt += f"\nUser's latest message: {input_text}\n\nWhat should I do next?"

            # Get the LLM's response
            response = await self.llm.ainvoke(prompt)
            
            # Handle both string and AIMessage responses
            if isinstance(response, str):
                response_text = response
            elif hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            
            if not response_text or not response_text.strip():
                logger.error(f"LLM returned empty response for input: {input_text}")
                raise RuntimeError("LLM returned empty response.")
            
            response_text = response_text.strip()
            
            # Check if the response contains a tool call
            if "TOOL_CALL:" in response_text:
                # Parse the tool call
                tool_call_line = response_text.split("TOOL_CALL:")[1].strip().split("\n")[0]
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
                "content": response_text
            }
                
        except Exception as e:
            logger.error(f"Error deciding next action: {e}")
            raise

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

    async def _summarize_tool_result(self, tool_name: str, tool_result: Any) -> str:
        """Summarize a tool result in a user-friendly way."""
        try:
            if tool_name == "delete_events_in_range":
                # For calendar deletions, provide detailed information about what was deleted
                if isinstance(tool_result, dict):
                    count = tool_result.get('count', 0)
                    events = tool_result.get('events', [])
                    
                    if count == 0:
                        return "I didn't find any events to delete in that time period."
                    
                    # Build a detailed response
                    response = f"I've deleted {count} event{'s' if count != 1 else ''} from your calendar:\n\n"
                    for event in events:
                        summary = event.get('summary', 'Untitled event')
                        start = event.get('start', '')
                        location = event.get('location', '')
                        
                        # Try to format the date nicely
                        try:
                            if start:
                                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                                formatted_time = start_dt.strftime('%I:%M %p on %B %d, %Y')
                                event_str = f"- {summary} at {formatted_time}"
                            else:
                                event_str = f"- {summary}"
                        except:
                            event_str = f"- {summary}"
                        
                        # Add location if available
                        if location:
                            event_str += f" ({location})"
                        
                        response += event_str + "\n"
                    
                    return response
                else:
                    # Fallback for old format or errors
                    if isinstance(tool_result, int):
                        if tool_result == 0:
                            return "I didn't find any events to delete in that time period."
                        elif tool_result == 1:
                            return "I've deleted 1 event from your calendar."
                        else:
                            return f"I've deleted {tool_result} events from your calendar."
                    return "I've cleared those events from your calendar."

            # For calendar event creation
            if tool_name == "create_calendar_event":
                if isinstance(tool_result, dict):
                    if tool_result.get("type") == "conflict":
                        conflicting_events = tool_result.get("conflicting_events", [])
                        conflict_msg = f"I found {len(conflicting_events)} conflicting event(s) at this time:\n\n"
                        for event in conflicting_events:
                            start = event['start'].get('dateTime', event['start'].get('date'))
                            summary = event.get('summary', 'Untitled event')
                            conflict_msg += f"- {summary} at {start}\n"
                        conflict_msg += "\nHow would you like to proceed?\n"
                        conflict_msg += "1. Skip: Don't create the new event\n"
                        conflict_msg += "2. Replace: Delete all conflicting events and create the new one\n"
                        conflict_msg += "3. Delete: Delete the first conflicting event and create the new one"
                        return conflict_msg
                    else:
                        # Successfully created event
                        event_id = tool_result.get('id')
                        summary = tool_result.get('summary', 'event')
                        start = tool_result.get('start', {}).get('dateTime', '')
                        
                        # Get the HTML link from the event response
                        html_link = tool_result.get('htmlLink', '')
                        if not html_link and event_id:
                            # If no htmlLink is provided, construct it using the event ID
                            import base64
                            # The event ID needs to be base64-encoded for the URL
                            encoded_id = base64.b64encode(event_id.encode()).decode()
                            html_link = f"https://www.google.com/calendar/event?eid={encoded_id}"
                        
                        if start:
                            try:
                                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                                formatted_time = start_dt.strftime('%I:%M %p on %B %d, %Y')
                                return f"Perfect! I've scheduled your {summary} for {formatted_time}. 📅 [View in Calendar]({html_link})"
                            except:
                                return f"Great! I've added the {summary} to your calendar. 📅 [View in Calendar]({html_link})"
                        else:
                            return f"Great! I've added the {summary} to your calendar. 📅 [View in Calendar]({html_link})"

            # For email sending
            if tool_name == "send_email":
                return "I've sent the email for you."

            # For task creation
            if tool_name == "create_task":
                if isinstance(tool_result, dict):
                    task_title = tool_result.get('title', 'task')
                    return f"I've created the task '{task_title}' for you."

            # For getting tasks
            if tool_name == "get_tasks":
                if isinstance(tool_result, list):
                    if not tool_result:
                        return "You don't have any tasks at the moment."
                    task_list = "\n".join([f"- {task.get('title', 'Untitled task')}" for task in tool_result])
                    return f"Here are your tasks:\n{task_list}"

            # For calendar event queries
            if tool_name == "get_calendar_events":
                if isinstance(tool_result, list):
                    if not tool_result:
                        return "You don't have any upcoming events scheduled."
                    event_list = []
                    for event in tool_result:
                        start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', ''))
                        if start:
                            try:
                                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                                formatted_time = start_dt.strftime('%I:%M %p on %B %d')
                                event_list.append(f"- {event.get('summary', 'Untitled event')} at {formatted_time}")
                            except:
                                event_list.append(f"- {event.get('summary', 'Untitled event')} at {start}")
                    return "Here are your upcoming events:\n" + "\n".join(event_list)

            # Default response if no specific formatting is defined
            return str(tool_result)

        except Exception as e:
            logger.error(f"Error summarizing tool result: {e}")
            return str(tool_result)

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
                if not summary:
                    logger.error(f"LLM returned empty summary for tool {last_tool} and result {tool_result}")
                    raise RuntimeError("LLM returned empty summary")
                responses.append(summary)
                state = "DONE"

        print(f"Final responses: {responses}")
        return responses

    async def _get_tool_confirmation_message(self, tool_name: str, args: str) -> str:
        """Get a confirmation message for a tool call."""
        try:
            prompt = f"""You are a helpful personal trainer AI assistant. The user has requested an action that requires using the {tool_name} tool.

Tool arguments: {args}

Please provide a natural, conversational response that:
1. For calendar deletions:
   - Be brief and direct
   - Just confirm what time period you'll be clearing
   - Don't ask for confirmation
   - Example: "I'll clear your calendar for March 20th."
2. For calendar events:
   - Mention the event title, time, and that you'll provide a link
3. For emails:
   - Mention the recipient and subject
4. For tasks:
   - Mention the task name and due date
5. For location searches:
   - Mention the location and what you're looking for
6. Avoid using technical terms or mentioning the tool name
7. Be encouraging and helpful
8. NEVER use generic responses like "I'll add that to your calendar" or "Your workout has been scheduled"
9. Always include specific details from the request

Example responses:
- "I'll schedule your Upper Body Workout for tomorrow at 10 AM, focusing on chest and shoulders. Once it's set up, I'll share a link so you can view all the details in your calendar."
- "I'll send an email to Coach Sarah (sarah@gym.com) with your latest progress report, titled 'Weekly Progress Update - Strength Gains'."
- "I'll create a task to track your daily protein intake (target: 150g) that will be due this Friday."

Please provide a natural, detailed response:"""

            response = await self.llm.ainvoke(prompt)
            if not response or not hasattr(response, 'content') or not response.content.strip():
                raise RuntimeError("LLM returned empty response")
            return response.content.strip()
        except Exception as e:
            logger.error(f"Error getting LLM confirmation message: {e}")
            raise

    async def process_messages(self, messages):
        """Process a list of messages and return a response."""
        if not self.agent:
            raise RuntimeError("Agent not initialized. Call async_init() first.")

        # Convert messages to LangChain format
        input_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    input_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    input_messages.append(AIMessage(content=content))
                elif role == "system":
                    input_messages.append(SystemMessage(content=content))
            else:
                input_messages.append(msg)

        # Use the agent_conversation_loop for multi-step orchestration
        responses = await self.agent_conversation_loop(input_messages)
        # Always return only the latest response as a string
        if isinstance(responses, list):
            return responses[-1] if responses else "No response generated"
        return responses

    async def process_messages_stream(self, messages):
        """Process a list of messages and yield responses as they become available."""
        if not self.agent:
            raise RuntimeError("Agent not initialized. Call async_init() first.")

        # Convert messages to LangChain format
        input_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    input_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    input_messages.append(AIMessage(content=content))
                elif role == "system":
                    input_messages.append(SystemMessage(content=content))
            else:
                input_messages.append(msg)

        # Use the streaming agent_conversation_loop for real-time responses
        async for response in self.agent_conversation_loop_stream(input_messages):
            yield response

    async def agent_conversation_loop_stream(self, user_input):
        """Stream-based orchestration to support multi-step agent actions with enforced tool result summarization."""
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
                if not summary:
                    logger.error(f"LLM returned empty summary for tool {last_tool} and result {tool_result}")
                    raise RuntimeError("LLM returned empty summary")
                yield summary
                state = "DONE"

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
        pacific_tz = pytz.timezone('America/Los_Angeles')
        now = datetime.now(pacific_tz)
        def build_prompt(input_text):
            return f"""Convert this natural language event description into a Google Calendar event JSON.\nCurrent time: {now.strftime('%Y-%m-%d %H:%M')} Pacific Time\n\nInput: \"{input_text}\"\n\nRespond ONLY with a valid JSON object, no text or explanation, and never repeat the input. The JSON must have these fields:\n- summary: Event title\n- start: Object with dateTime (ISO format with -07:00 timezone) and timeZone (\"America/Los_Angeles\")\n- end: Object with dateTime (ISO format with -07:00 timezone) and timeZone (\"America/Los_Angeles\")\n- description: Brief description (optional)\n- location: Event location (optional)\n\nRules:\n1. If no time is specified, use 6:00 PM tomorrow\n2. If no duration is specified, make it 1 hour\n3. Always use Pacific Time (-07:00)\n4. For \"tomorrow\", use tomorrow's date\n5. For \"today\", use today's date\n6. For times like \"9 AM\", convert to 24-hour format (09:00)\n\nExample:\n{{\n    \"summary\": \"Workout Session\",\n    \"start\": {{\n        \"dateTime\": \"2024-03-20T18:00:00-07:00\",\n        \"timeZone\": \"America/Los_Angeles\"\n    }},\n    \"end\": {{\n        \"dateTime\": \"2024-03-20T19:00:00-07:00\",\n        \"timeZone\": \"America/Los_Angeles\"\n    }},\n    \"description\": \"General fitness workout\",\n    \"location\": \"Gym\"\n}}\n"""
        last_json_string = None
        for attempt in range(2):  # Try twice
            try:
                messages = [
                    SystemMessage(content="You are a helpful assistant that converts natural language to Google Calendar event JSON. Always return valid JSON only. Never use hardcoded dates - always use relative dates based on the current date."),
                    HumanMessage(content=build_prompt(natural_language_input))
                ]
                response = await self.llm.ainvoke(messages)
                json_string = response.content.strip()
                json_string = json_string.replace('```json', '').replace('```', '').strip()
                last_json_string = json_string
                event_data = json.loads(json_string)
                # Ensure start and end are properly formatted
                for time_field in ['start', 'end']:
                    if time_field in event_data:
                        if isinstance(event_data[time_field], str):
                            dt = dateparser.parse(event_data[time_field], settings={'PREFER_DATES_FROM': 'future'})
                            if dt:
                                if dt.tzinfo is None:
                                    dt = pacific_tz.localize(dt)
                                event_data[time_field] = {
                                    'dateTime': dt.isoformat(),
                                    'timeZone': 'America/Los_Angeles'
                                }
                        elif isinstance(event_data[time_field], dict):
                            if 'dateTime' in event_data[time_field]:
                                dt = dateparser.parse(event_data[time_field]['dateTime'], settings={'PREFER_DATES_FROM': 'future'})
                                if dt:
                                    if dt.tzinfo is None:
                                        dt = pacific_tz.localize(dt)
                                    event_data[time_field]['dateTime'] = dt.isoformat()
                                    event_data[time_field]['timeZone'] = 'America/Los_Angeles'
                return json.dumps(event_data)
            except Exception as e:
                logger.error(f"Attempt {attempt+1}: Error converting natural language to JSON: {e}. LLM output: {last_json_string}")
                if attempt == 0:
                    continue
                else:
                    raise ValueError(f"LLM did not return valid JSON for event. LLM output: {last_json_string}")

    async def _execute_tool(self, tool_name: str, args: Union[str, Dict[str, Any]]) -> Any:
        """Execute a tool and return its result."""
        try:
            # Find the matching tool
            tool = next((t for t in self.tools if t.name == tool_name), None)
            if not tool:
                raise ValueError(f"Unknown tool: {tool_name}")

            # Convert string args to dict if needed
            if isinstance(args, str):
                # Special handling for delete_events_in_range
                if tool_name == "delete_events_in_range":
                    # Parse pipe-separated format: start_time|end_time
                    parts = args.strip('"').split("|")
                    if len(parts) >= 2:
                        args = {
                            "start_time": parts[0],
                            "end_time": parts[1]
                        }
                    else:
                        raise ValueError(f"Invalid time range format. Expected 'start_time|end_time', got: {args}")
                
                # Special handling for create_calendar_event
                elif tool_name == "create_calendar_event":
                    try:
                        input_text = args.strip('"')
                        # Convert natural language to calendar event JSON
                        json_string = await self._convert_natural_language_to_calendar_json(input_text)
                        try:
                            # Parse the JSON string
                            args = json.loads(json_string)
                        except json.JSONDecodeError as e:
                            logger.error(f"Error parsing calendar event JSON: {e}")
                            raise ValueError(f"Invalid calendar event JSON format: {json_string}")
                        # Validate the required fields
                        if not isinstance(args, dict):
                            raise ValueError("Invalid calendar event format: not a dictionary")
                        required_fields = ['summary', 'start', 'end']
                        missing_fields = [field for field in required_fields if field not in args]
                        if missing_fields:
                            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
                        # Ensure start and end are properly formatted
                        for time_field in ['start', 'end']:
                            if not isinstance(args[time_field], dict):
                                raise ValueError(f"Invalid {time_field} format: not a dictionary")
                            if 'dateTime' not in args[time_field]:
                                raise ValueError(f"Missing dateTime in {time_field}")
                            if 'timeZone' not in args[time_field]:
                                args[time_field]['timeZone'] = 'America/Los_Angeles'
                    except Exception as e:
                        logger.error(f"Error processing calendar event: {e}")
                        # Propagate the error message from _convert_natural_language_to_calendar_json
                        raise ValueError(str(e))
                
                # Special handling for send_email
                elif tool_name == "send_email":
                    # Parse pipe-separated format: recipient|subject|body
                    parts = args.strip('"').split("|")
                    if len(parts) >= 3:
                        args = {
                            "to": parts[0],
                            "subject": parts[1],
                            "body": parts[2]
                        }
                    else:
                        raise ValueError(f"Invalid email format. Expected 'recipient|subject|body', got: {args}")
                else:
                    # For other tools, just pass the string as is
                    args = {"query": args.strip('"')} if args else {}

            # Execute the tool
            logger.info(f"Executing tool {tool_name} with args: {args}")
            result = await tool.func(args) if asyncio.iscoroutinefunction(tool.func) else tool.func(args)
            logger.info(f"Tool {tool_name} returned: {result}")
            return result

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            raise

    def _create_tools(self):
        """Create the tools for the agent."""
        # Clear existing tools
        self.tools = []
        
        if self.calendar_service:
            logger.debug("Adding Calendar tools...")
            self.tools.extend([
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
                )
            ])
        if self.gmail_service:
            logger.debug("Adding Gmail tools...")
            self.tools.extend([
                Tool(
                    name="send_email",
                    func=self.gmail_service.send_message,
                    description="Send an email to a recipient"
                )
            ])
        if self.tasks_service:
            logger.debug("Adding Tasks tools...")
            self.tools.extend([
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
            self.tools.extend([
                Tool(
                    name="search_drive",
                    func=self.drive_service.search_files,
                    description="Search for files in Google Drive"
                )
            ])
        if self.sheets_service:
            logger.debug("Adding Sheets tools...")
            self.tools.extend([
                Tool(
                    name="get_sheet_data",
                    func=self.sheets_service.get_sheet_data,
                    description="Get data from a Google Sheet"
                )
            ])
        if self.maps_service:
            logger.debug("Adding Maps tools...")
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
        logger.info(f"Created {len(self.tools)} tools for agent")
        return self.tools

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

