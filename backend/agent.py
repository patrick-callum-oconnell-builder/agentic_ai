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
from langchain.schema import BaseMessage
import re
from backend.tools.preferences_tools import add_preference_to_kg

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

Always be professional, encouraging, and focused on helping the user achieve their fitness goals.

IMPORTANT RULES:
1. ONLY use tools when explicitly needed for the user's request
2. For calendar events:
   - ONLY use create_calendar_event when the user explicitly wants to schedule something
   - ONLY use get_calendar_events when the user asks to see their schedule
   - ONLY use delete_events_in_range when the user wants to clear their calendar
   - If the user asks to see their schedule, list events only for the requested time frame (e.g., 'this week', 'next week', 'today'). Do NOT schedule a new event unless explicitly requested.
3. For emails:
   - ONLY use send_email when the user wants to send a message
4. For tasks:
   - ONLY use create_task when the user wants to create a task
5. For location searches:
   - ONLY use search_location when the user wants to find a place
6. For sheets:
   - ONLY use create_workout_tracker when the user wants to create a new workout tracking spreadsheet
   - ONLY use add_workout_entry when the user wants to log a workout
   - ONLY use add_nutrition_entry when the user wants to log nutrition information
   - ONLY use get_sheet_data when the user wants to view sheet data

When using tools:
1. For calendar events:
   - Use create_calendar_event with a JSON object containing:
     - summary: Event title
     - start: Object with dateTime and timeZone
     - end: Object with dateTime and timeZone
     - description: Event details
     - location: Event location
   - Use get_calendar_events with an empty string to list events
   - Use delete_events_in_range with start_time|end_time format
2. For emails:
   - Use send_email with recipient|subject|body format
3. For tasks:
   - Use create_task with task_name|due_date format
4. For location searches:
   - Use search_location with location|query format
   - Use find_nearby_workout_locations with location|radius format
     Example: find_nearby_workout_locations: "One Infinite Loop, Cupertino, CA 95014|30"
5. For sheets:
   - Use create_workout_tracker with title format
   - Use add_workout_entry with spreadsheet_id|date|workout_type|duration|calories|notes format
   - Use add_nutrition_entry with spreadsheet_id|date|meal|calories|protein|carbs|fat|notes format
   - Use get_sheet_data with spreadsheet_id|range_name format

Example tool calls:
- create_calendar_event: {{"summary": "Upper Body Workout", "start": {{"dateTime": "2025-06-18T10:00:00-07:00", "timeZone": "America/Los_Angeles"}}, "end": {{"dateTime": "2025-06-18T11:00:00-07:00", "timeZone": "America/Los_Angeles"}}, "description": "Focus on chest and shoulders", "location": "Gym"}}
- get_calendar_events: ""
- delete_events_in_range: "2025-06-18T00:00:00-07:00|2025-06-18T23:59:59-07:00"
- send_email: "coach@gym.com|Weekly Progress Update|Here's your progress report..."
- create_task: "Track protein intake|2025-06-21"
- search_location: "San Francisco|gym"
- create_workout_tracker: "My Workout Tracker"
- add_workout_entry: "spreadsheet_id|2025-06-17|Upper Body|60|300|Focus on chest and shoulders"
- add_nutrition_entry: "spreadsheet_id|2025-06-17|Lunch|500|30|50|20|Post-workout meal"
- get_sheet_data: "spreadsheet_id|Workouts!A1:E10"

IMPORTANT: Only use tools when explicitly needed for the user's request. Do not make unnecessary tool calls.

When the user asks to schedule a workout:
1. ALWAYS use create_calendar_event with a properly formatted JSON object
2. ALWAYS include timeZone in the start and end times
3. ALWAYS set the end time to be 1 hour after the start time unless specified otherwise
4. ALWAYS include a descriptive summary and location
5. ALWAYS use the format: TOOL_CALL: create_calendar_event {{"summary": "...", "start": {{"dateTime": "...", "timeZone": "..."}}, "end": {{"dateTime": "...", "timeZone": "..."}}, "description": "...", "location": "..."}}"""

class FindNearbyWorkoutLocationsInput(BaseModel):
    lat: float = Field(..., description="Latitude of the location")
    lng: float = Field(..., description="Longitude of the location")
    radius: int = Field(5000, description="Search radius in meters (default 5000)")

# Helper function to extract time frame from user message
def extract_timeframe_from_text(text: str) -> Optional[Dict[str, str]]:
    """Extract timeframe from text and return timeMin and timeMax in ISO format."""
    try:
        now = datetime.now(dt_timezone.utc)
        
        # Common time frame patterns
        if 'this week' in text.lower():
            # Set time_min to start of current week (Monday)
            start_of_week = now - timedelta(days=now.weekday())
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            # Set time_max to end of week (Sunday)
            end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
            return {
                'timeMin': start_of_week.isoformat(),
                'timeMax': end_of_week.isoformat()
            }
        elif 'next week' in text.lower():
            # Set time_min to start of next week (Monday)
            start_of_week = now - timedelta(days=now.weekday()) + timedelta(days=7)
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            # Set time_max to end of next week (Sunday)
            end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
            return {
                'timeMin': start_of_week.isoformat(),
                'timeMax': end_of_week.isoformat()
            }
        elif 'today' in text.lower():
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1, microseconds=-1)
            return {
                'timeMin': start_of_day.isoformat(),
                'timeMax': end_of_day.isoformat()
            }
        elif 'tomorrow' in text.lower():
            start_of_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1, microseconds=-1)
            return {
                'timeMin': start_of_day.isoformat(),
                'timeMax': end_of_day.isoformat()
            }
        return None
    except Exception as e:
        logger.error(f"Error extracting time frame: {e}")
        return None

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
            logger.debug("Adding Sheets tools...")
            self.tools.extend([
                Tool(
                    name="get_sheet_data",
                    func=self.sheets_service.get_sheet_data,
                    description="Get data from a Google Sheet"
                ),
                Tool(
                    name="create_workout_tracker",
                    func=self.sheets_service.create_workout_tracker,
                    description="Create a new workout tracking spreadsheet"
                ),
                Tool(
                    name="add_workout_entry",
                    func=self.sheets_service.add_workout_entry,
                    description="Add a workout entry to the tracker"
                ),
                Tool(
                    name="add_nutrition_entry",
                    func=self.sheets_service.add_nutrition_entry,
                    description="Add a nutrition entry to the tracker"
                )
            ])
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
        self.tools.append(
            Tool(
                name="add_preference_to_kg",
                func=add_preference_to_kg,
                description="Add a user preference to the knowledge graph"
            )
        )
        
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

    async def _format_tool_response(self, tool_name: str, tool_result: Any) -> str:
        """Format a tool response into a user-friendly message."""
        try:
            # First try to get a natural language summary from the LLM
            summary = await self._summarize_tool_result(tool_name, tool_result)
            if not summary:
                raise RuntimeError("LLM returned empty summary")
            return summary
        except Exception as e:
            logger.error(f"Error formatting tool response: {e}")
            # Provide a more detailed fallback response based on the tool type
            if tool_name == "create_calendar_event":
                if isinstance(tool_result, dict) and 'id' in tool_result:
                    return f"I've successfully added '{tool_result.get('summary', 'the event')}' to your calendar. You can view it in your calendar app."
                elif isinstance(tool_result, dict) and 'conflicting_events' in tool_result:
                    return f"I couldn't add the event due to a conflict: {tool_result.get('message', 'There is a conflict with another event.')}"
                else:
                    return "I've added the event to your calendar. You can view it in your calendar app."
            elif tool_name == "get_calendar_events":
                if not tool_result:
                    return "You don't have any upcoming events."
                events = []
                for event in tool_result:
                    start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', ''))
                    summary = event.get('summary', 'Untitled Event')
                    events.append(f"- {summary} at {start}")
                return "Here are your upcoming events:\n" + "\n".join(events)
            elif tool_name == "find_nearby_workout_locations":
                if not tool_result:
                    return "I couldn't find any workout locations nearby."
                locations = []
                for location in tool_result:
                    name = location.get('name', 'Unknown Location')
                    address = location.get('address', 'No address available')
                    rating = location.get('rating', 'No rating')
                    locations.append(f"- {name} at {address} (Rating: {rating})")
                return "Here are some workout locations nearby:\n" + "\n".join(locations)
            else:
                return f"I've completed your request. You can check the details in your {tool_name.replace('_', ' ')}."

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
            
            # Preference detection (integrated)
            preference = await self.extract_preference_llm(input_text)
            if preference:
                return {
                    "type": "tool_call",
                    "tool": "add_preference_to_kg",
                    "args": preference
                }

            # Get current time and date
            current_time = datetime.now().strftime("%I:%M %p")
            current_date = datetime.now().strftime("%A, %B %d, %Y")

            # Format the tools list
            formatted_tools = "\n".join([
                f"- {tool.name}: {tool.description}"
                for tool in self.tools
            ])

            # Create the system prompt with tool descriptions
            system_prompt = f"""You are a helpful personal trainer AI assistant. You have access to the following tools:

{formatted_tools}

Current time: {current_time}
Current date: {current_date}

IMPORTANT RULES:
1. ONLY use tools when explicitly needed for the user's request
2. For calendar events:
   - ONLY use create_calendar_event when the user explicitly wants to schedule something
   - ONLY use get_calendar_events when the user asks to see their schedule
   - ONLY use delete_events_in_range when the user wants to clear their calendar
   - If the user asks to see their schedule, list events only for the requested time frame (e.g., 'this week', 'next week', 'today'). Do NOT schedule a new event unless explicitly requested.
3. For emails:
   - ONLY use send_email when the user wants to send a message
4. For tasks:
   - ONLY use create_task when the user wants to create a task
5. For location searches:
   - ONLY use search_location when the user wants to find a place
6. For sheets:
   - ONLY use create_workout_tracker when the user wants to create a new workout tracking spreadsheet
   - ONLY use add_workout_entry when the user wants to log a workout
   - ONLY use add_nutrition_entry when the user wants to log nutrition information
   - ONLY use get_sheet_data when the user wants to view sheet data

When using tools:
1. For calendar events:
   - Use create_calendar_event with a JSON object containing:
     - summary: Event title
     - start: Object with dateTime and timeZone
     - end: Object with dateTime and timeZone
     - description: Event details
     - location: Event location
   - Use get_calendar_events with an empty string to list events
   - Use delete_events_in_range with start_time|end_time format
2. For emails:
   - Use send_email with recipient|subject|body format
3. For tasks:
   - Use create_task with task_name|due_date format
4. For location searches:
   - Use search_location with location|query format
   - Use find_nearby_workout_locations with location|radius format
     Example: find_nearby_workout_locations: "One Infinite Loop, Cupertino, CA 95014|30"
5. For sheets:
   - Use create_workout_tracker with title format
   - Use add_workout_entry with spreadsheet_id|date|workout_type|duration|calories|notes format
   - Use add_nutrition_entry with spreadsheet_id|date|meal|calories|protein|carbs|fat|notes format
   - Use get_sheet_data with spreadsheet_id|range_name format

Example tool calls:
- create_calendar_event: {{"summary": "Upper Body Workout", "start": {{"dateTime": "2025-06-18T10:00:00-07:00", "timeZone": "America/Los_Angeles"}}, "end": {{"dateTime": "2025-06-18T11:00:00-07:00", "timeZone": "America/Los_Angeles"}}, "description": "Focus on chest and shoulders", "location": "Gym"}}
- get_calendar_events: ""
- delete_events_in_range: "2025-06-18T00:00:00-07:00|2025-06-18T23:59:59-07:00"
- send_email: "coach@gym.com|Weekly Progress Update|Here's your progress report..."
- create_task: "Track protein intake|2025-06-21"
- search_location: "San Francisco|gym"
- create_workout_tracker: "My Workout Tracker"
- add_workout_entry: "spreadsheet_id|2025-06-17|Upper Body|60|300|Focus on chest and shoulders"
- add_nutrition_entry: "spreadsheet_id|2025-06-17|Lunch|500|30|50|20|Post-workout meal"
- get_sheet_data: "spreadsheet_id|Workouts!A1:E10"

IMPORTANT: Only use tools when explicitly needed for the user's request. Do not make unnecessary tool calls.

When the user asks to schedule a workout:
1. ALWAYS use create_calendar_event with a properly formatted JSON object
2. ALWAYS include timeZone in the start and end times
3. ALWAYS set the end time to be 1 hour after the start time unless specified otherwise
4. ALWAYS include a descriptive summary and location
5. ALWAYS use the format: TOOL_CALL: create_calendar_event {{"summary": "...", "start": {{"dateTime": "...", "timeZone": "..."}}, "end": {{"dateTime": "...", "timeZone": "..."}}, "description": "...", "location": "..."}}"""

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
                tool_call_line = response_text.split("TOOL_CALL:")[1].strip().split("\n")[0]
                parts = tool_call_line.split(" ", 1)
                if len(parts) >= 2:
                    tool_name = parts[0].strip().rstrip(":")
                    tool_args = parts[1].strip()
                    # If get_calendar_events, override args with timeframe if present in user message
                    if tool_name == "get_calendar_events":
                        timeframe = extract_timeframe_from_text(input_text)
                        if timeframe:
                            tool_args = f'"{timeframe}"'
                    logger.info(f"[TOOL_CALL] Tool selected: {tool_name}, Args: {tool_args}")
                    return {
                        "type": "tool_call",
                        "tool": tool_name,
                        "args": tool_args
                    }
            # Fallback: detect lines like 'find_nearby_workout_locations: ...' as tool calls
            for tool in self.tools:
                prefix = f"{tool.name}:"
                if response_text.strip().startswith(prefix):
                    tool_args = response_text.strip()[len(prefix):].strip()
                    return {
                        "type": "tool_call",
                        "tool": tool.name,
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

    async def process_tool_result(self, tool_name: str, result: Any) -> str:
        """Process the result of a tool execution and return a user-friendly response."""
        try:
            # Special handling for delete_events_in_range
            if tool_name == "delete_events_in_range":
                if isinstance(result, int):
                    if result == 0:
                        return "I've checked your calendar for the specified time period, but there were no events to delete."
                    elif result == 1:
                        return "I've removed 1 event from your calendar for the specified time period."
                    else:
                        return f"I've removed {result} events from your calendar for the specified time period."
                else:
                    return "I've cleared your calendar for the specified time period."

            # Create a detailed prompt for the LLM to summarize the tool result
            prompt = f"""You are a helpful personal trainer AI assistant. Summarize the result of the {tool_name} tool in a user-friendly way.

Tool result: {json.dumps(result, default=str)}

Guidelines:
1. Be concise but informative
2. Use natural, conversational language
3. Format any dates, times, or numbers in a readable way
4. If there are any errors or issues, explain them clearly
5. If the result is a list or complex data, summarize the key points
6. Use markdown formatting for better readability
7. For calendar events, ALWAYS include:
   - Event title
   - Date and time in a readable format
   - A clickable link to the event using markdown [Event Link](url)
   - Any other relevant details
8. For workout locations, include:
   - Name of the location
   - Address
   - Distance if available
9. For tasks, include:
   - Task name
   - Due date
   - Priority if available
10. For emails, include:
    - Recipient
    - Subject
    - Status of the send operation

Example responses:
- For calendar events: "I've scheduled your Upper Body Workout for tomorrow at 10 AM at the Downtown Gym. You can view all the details here: [Event Link](https://calendar.google.com/event/...)"
- For workout locations: "I found a great gym nearby: Fitness First at 123 Main St, just 0.5 miles away. They have all the equipment you need for your workout routine."
- For tasks: "I've added 'Track daily protein intake' to your task list, due this Friday. I'll remind you about it as the deadline approaches."

Please provide a natural, detailed response:"""

            messages = [
                SystemMessage(content="You are a helpful personal trainer AI assistant. Always respond in clear, natural language, never as a code block or raw data. Be encouraging and focused on helping the user achieve their fitness goals."),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)
            if not response or not hasattr(response, 'content') or not response.content.strip():
                raise RuntimeError("LLM returned empty response")
            
            summary = response.content.strip()
            
            # Validate that the summary is not just a raw tool result
            if json.dumps(result, default=str) in summary:
                raise RuntimeError("LLM returned raw tool result instead of a summary")
            
            # If get_calendar_events and summary does not mention any event titles, fall back to default event list
            if tool_name == "get_calendar_events":
                event_titles = [event.get('summary', '') for event in result if isinstance(event, dict)]
                if not any(title in summary for title in event_titles):
                    # Fallback: list the events
                    if not event_titles:
                        return "You have no upcoming events in the requested time frame."
                    events = []
                    for event in result:
                        start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', ''))
                        summary_title = event.get('summary', 'Untitled Event')
                        events.append(f"- {summary_title} at {start}")
                    return "Here are your upcoming events in the requested time frame:\n" + "\n".join(events)
            return summary

        except Exception as e:
            logger.error(f"Error summarizing tool result: {e}")
            # Provide a basic fallback response based on the tool type
            if tool_name == "create_calendar_event":
                return "I've scheduled your workout in your calendar. You can check your calendar app for the details."
            elif tool_name == "get_calendar_events":
                return "I'll list your upcoming events."
            elif tool_name == "find_nearby_workout_locations":
                if not result:
                    return "I couldn't find any workout locations nearby."
                locations = []
                for location in result:
                    name = location.get('name', 'Unknown Location')
                    address = location.get('address', 'No address available')
                    rating = location.get('rating', 'No rating')
                    locations.append(f"- {name} at {address} (Rating: {rating})")
                return "Here are some workout locations nearby:\n" + "\n".join(locations)
            elif tool_name == "delete_events_in_range":
                if isinstance(result, int):
                    return f"I've removed {result} events from your calendar."
                return "I've cleared your calendar for the specified time period."
            else:
                return f"I've completed your request. You can check the details in your {tool_name.replace('_', ' ')}."

    async def process_messages(self, messages: List[BaseMessage]) -> str:
        """Process a list of messages and return a response as a string."""
        try:
            # Accept both dict and HumanMessage input
            user_message = None
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    user_message = msg
                    break
                elif isinstance(msg, dict) and msg.get("role") == "user":
                    user_message = HumanMessage(content=msg.get("content", ""))
                    break
            if not user_message:
                return "I didn't receive any user message to process."

            # Use the agent_conversation_loop for proper three-step process
            responses = await self.agent_conversation_loop(user_message.content)
            return "\n".join(responses)

        except Exception as e:
            logger.error(f"Error processing messages: {str(e)}")
            return f"I encountered an error: {str(e)}"

    async def process_messages_stream(self, messages):
        """Process messages and return a streaming response with multi-step tool execution."""
        try:
            # Convert messages to LangChain format
            input_messages = []
            for msg in messages:
                converted = self._convert_message(msg)
                if converted:
                    input_messages.append(converted)
            
            if not input_messages:
                yield "I didn't receive any valid messages to process."
                return
            
            # Get the last user message
            user_message = input_messages[-1]
            if not isinstance(user_message, HumanMessage):
                yield "I need a user message to process."
                return
            
            # Multi-step process: decide action → confirm → execute → summarize
            state = "AGENT_THINKING"
            history = [user_message.content]
            agent_action = None
            tool_result = None
            last_tool = None

            while state != "DONE":
                if state == "AGENT_THINKING":
                    agent_action = await self.decide_next_action(history)
                    if agent_action["type"] == "message":
                        yield agent_action["content"]
                        state = "DONE"
                    elif agent_action["type"] == "tool_call":
                        last_tool = agent_action["tool"]
                        # Send confirmation message before calling tool
                        confirmation_message = await self._get_tool_confirmation_message(last_tool, agent_action["args"])
                        yield confirmation_message
                        state = "AGENT_TOOL_CALL"
                    else:
                        state = "DONE"
                elif state == "AGENT_TOOL_CALL":
                    tool_result = await self._execute_tool(agent_action["tool"], agent_action["args"])
                    # Add the tool result as a message in the history
                    history.append(f"TOOL RESULT: {tool_result}")
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
                
        except Exception as e:
            logger.error(f"Error in process_messages_stream: {e}")
            yield f"Error processing messages: {str(e)}"

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
        """Execute a tool with the given arguments."""
        try:
            # Find the tool
            tool = next((t for t in self.tools if t.name == tool_name), None)
            if not tool:
                raise ValueError(f"Tool {tool_name} not found")

            # Special handling for add_preference_to_kg
            if tool_name == "add_preference_to_kg":
                # If args is a dict with 'query', extract the value
                if isinstance(args, dict) and 'query' in args:
                    arg_val = args['query']
                else:
                    arg_val = args
                result = await tool.func(arg_val) if asyncio.iscoroutinefunction(tool.func) else tool.func(arg_val)
                logger.info(f"Tool {tool_name} returned: {result}")
                return result

            # Convert string args to dict if needed
            if isinstance(args, str):
                # Special handling for get_calendar_events
                if tool_name == "get_calendar_events":
                    # Extract time frame from the user's query
                    timeframe = extract_timeframe_from_text(args)
                    if timeframe:
                        # Override the args with the extracted time frame
                        args = timeframe
                    else:
                        # Default to upcoming events if no time frame specified
                        args = {"timeMin": datetime.now(dt_timezone.utc).isoformat()}
                # Special handling for delete_events_in_range
                elif tool_name == "delete_events_in_range":
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
                # Special handling for find_nearby_workout_locations
                elif tool_name == "find_nearby_workout_locations":
                    # Parse pipe-separated format: address|radius
                    parts = args.strip('"').split("|")
                    if len(parts) == 2:
                        address = parts[0].strip()
                        try:
                            radius = int(parts[1].strip())
                        except Exception:
                            radius = 30
                        # Geocode the address to get lat/lng
                        if hasattr(self.maps_service, 'geocode_address'):
                            lat, lng = await self.maps_service.geocode_address(address)
                            args = {"lat": lat, "lng": lng, "radius": radius}
                        else:
                            args = {"location": address, "radius": radius}
                    else:
                        args = {"location": args.strip('"')}
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
                ),
                Tool(
                    name="create_workout_tracker",
                    func=self.sheets_service.create_workout_tracker,
                    description="Create a new workout tracking spreadsheet"
                ),
                Tool(
                    name="add_workout_entry",
                    func=self.sheets_service.add_workout_entry,
                    description="Add a workout entry to the tracker"
                ),
                Tool(
                    name="add_nutrition_entry",
                    func=self.sheets_service.add_nutrition_entry,
                    description="Add a nutrition entry to the tracker"
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
        self.tools.append(
            Tool(
                name="add_preference_to_kg",
                func=add_preference_to_kg,
                description="Add a user preference to the knowledge graph"
            )
        )
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
        """Convert a message to the format expected by the agent."""
        if isinstance(msg, dict):
            if msg.get('role') == 'user':
                return HumanMessage(content=msg.get('content', ''))
            elif msg.get('role') == 'assistant':
                return AIMessage(content=msg.get('content', ''))
            else:
                return HumanMessage(content=str(msg))
        elif isinstance(msg, str):
            return HumanMessage(content=msg)
        else:
            return HumanMessage(content=str(msg))

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

    async def _summarize_tool_result(self, tool_name: str, tool_result: Any) -> str:
        """Summarize a tool result using the LLM to provide a natural, user-friendly response."""
        try:
            # Special handling for delete_events_in_range
            if tool_name == "delete_events_in_range":
                if isinstance(tool_result, int):
                    if tool_result == 0:
                        return "I've checked your calendar for the specified time period, but there were no events to delete."
                    elif tool_result == 1:
                        return "I've removed 1 event from your calendar for the specified time period."
                    else:
                        return f"I've removed {tool_result} events from your calendar for the specified time period."
                else:
                    return "I've cleared your calendar for the specified time period."

            # Create a detailed prompt for the LLM to summarize the tool result
            prompt = f"""You are a helpful personal trainer AI assistant. Summarize the result of the {tool_name} tool in a user-friendly way.

Tool result: {json.dumps(tool_result, default=str)}

Guidelines:
1. Be concise but informative
2. Use natural, conversational language
3. Format any dates, times, or numbers in a readable way
4. If there are any errors or issues, explain them clearly
5. If the result is a list or complex data, summarize the key points
6. Use markdown formatting for better readability
7. For calendar events, ALWAYS include:
   - Event title
   - Date and time in a readable format
   - A clickable link to the event using markdown [Event Link](url)
   - Any other relevant details
8. For workout locations, include:
   - Name of the location
   - Address
   - Distance if available
9. For tasks, include:
   - Task name
   - Due date
   - Priority if available
10. For emails, include:
    - Recipient
    - Subject
    - Status of the send operation

Example responses:
- For calendar events: "I've scheduled your Upper Body Workout for tomorrow at 10 AM at the Downtown Gym. You can view all the details here: [Event Link](https://calendar.google.com/event/...)"
- For workout locations: "I found a great gym nearby: Fitness First at 123 Main St, just 0.5 miles away. They have all the equipment you need for your workout routine."
- For tasks: "I've added 'Track daily protein intake' to your task list, due this Friday. I'll remind you about it as the deadline approaches."

Please provide a natural, detailed response:"""

            messages = [
                SystemMessage(content="You are a helpful personal trainer AI assistant. Always respond in clear, natural language, never as a code block or raw data. Be encouraging and focused on helping the user achieve their fitness goals."),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)
            if not response or not hasattr(response, 'content') or not response.content.strip():
                raise RuntimeError("LLM returned empty response")
            
            summary = response.content.strip()
            
            # Validate that the summary is not just a raw tool result
            if json.dumps(tool_result, default=str) in summary:
                raise RuntimeError("LLM returned raw tool result instead of a summary")
            
            # If get_calendar_events and summary does not mention any event titles, fall back to default event list
            if tool_name == "get_calendar_events":
                event_titles = [event.get('summary', '') for event in tool_result if isinstance(event, dict)]
                if not any(title in summary for title in event_titles):
                    # Fallback: list the events
                    if not event_titles:
                        return "You have no upcoming events in the requested time frame."
                    events = []
                    for event in tool_result:
                        start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', ''))
                        summary_title = event.get('summary', 'Untitled Event')
                        events.append(f"- {summary_title} at {start}")
                    return "Here are your upcoming events in the requested time frame:\n" + "\n".join(events)
            return summary

        except Exception as e:
            logger.error(f"Error summarizing tool result: {e}")
            # Provide a basic fallback response based on the tool type
            if tool_name == "create_calendar_event":
                return "I've scheduled your workout in your calendar. You can check your calendar app for the details."
            elif tool_name == "get_calendar_events":
                return "I'll list your upcoming events."
            elif tool_name == "find_nearby_workout_locations":
                if not tool_result:
                    return "I couldn't find any workout locations nearby."
                locations = []
                for location in tool_result:
                    name = location.get('name', 'Unknown Location')
                    address = location.get('address', 'No address available')
                    rating = location.get('rating', 'No rating')
                    locations.append(f"- {name} at {address} (Rating: {rating})")
                return "Here are some workout locations nearby:\n" + "\n".join(locations)
            elif tool_name == "delete_events_in_range":
                if isinstance(tool_result, int):
                    return f"I've removed {tool_result} events from your calendar."
                return "I've cleared your calendar for the specified time period."
            else:
                return f"I've completed your request. You can check the details in your {tool_name.replace('_', ' ')}."

    async def extract_preference_llm(self, text: str) -> Optional[str]:
        """Use the LLM to extract a user preference from text. Returns the preference string or None."""
        prompt = (
            "You are an AI assistant that extracts user preferences from text. "
            "Return ONLY the preference (e.g., 'pizza', 'martial arts', 'strength training'), "
            "or 'None' if no clear preference is found. Do not include any explanation or extra text.\n"
            f"Text: {text}"
        )
        messages = [
            SystemMessage(content="You are an AI assistant that extracts user preferences from text. Respond with only the preference or 'None'."),
            HumanMessage(content=prompt)
        ]
        response = await self.llm.ainvoke(messages)
        preference = response.content.strip()
        if preference.lower() == 'none' or not preference:
            return None
        return preference

    async def _get_tool_confirmation_message(self, tool_name: str, args: str) -> str:
        """Get a confirmation message for a tool call.
        
        This method generates a simple statement of what action the agent is about to take.
        It does not ask for confirmation - that's handled by the agent's conversation flow.
        """
        try:
            # Create a prompt that guides the LLM to generate a simple action statement
            prompt = f"""You are a helpful personal trainer AI assistant. The user has requested an action that requires using the {tool_name} tool.

Tool arguments: {args}

Please provide a simple, natural statement that:
1. Clearly states what action will be taken
2. Includes the key details from the arguments in a user-friendly format
3. Is concise and context-appropriate
4. Does NOT ask for confirmation or end with a question

Example formats:
- For calendar events: "I'll schedule a [workout type] for [time] at [location]"
- For location searches: "I'll search for [location type] near [location]"
- For task creation: "I'll create a task to [task description] due [date]"
- For calendar clearing: "I'll clear your calendar for [time period]"
- For preferences: "I'll remember that you like [preference]"

Please provide the action statement:"""

            messages = [
                SystemMessage(content="You are a helpful personal trainer AI assistant. Always respond in clear, natural language. Be concise and direct in stating what action you're about to take."),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)
            return response.content.strip() if hasattr(response, 'content') else str(response)

        except Exception as e:
            logger.error(f"Error generating tool confirmation message: {e}")
            return "I'm about to process your request."

