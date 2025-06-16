import os
import sys
import json
import logging
import asyncio
import ast
from datetime import datetime, timedelta
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
    def __init__(self, calendar_service, gmail_service, tasks_service, drive_service, sheets_service, maps_service):
        self.calendar_service = calendar_service
        self.gmail_service = gmail_service
        self.tasks_service = tasks_service
        self.drive_service = drive_service
        self.sheets_service = sheets_service
        self.maps_service = maps_service
        self.agent = None
        self.state_manager = None

    async def async_init(self):
        """Async initialization method to set up the agent workflow."""
        self.agent = await self._create_agent_workflow()
        self.state_manager = StateManager()
        return self

    async def _create_agent_workflow(self):
        """Create the agent workflow asynchronously."""
        # Create the tools
        tools = [
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
                name="send_email",
                func=self.gmail_service.send_message,
                description="Send an email to a recipient"
            ),
            Tool(
                name="create_task",
                func=self.tasks_service.create_task,
                description="Create a new task"
            ),
            Tool(
                name="get_tasks",
                func=self.tasks_service.get_tasks,
                description="Get tasks from the task list"
            ),
            Tool(
                name="search_drive",
                func=self.drive_service.list_files,
                description="Search for files in Google Drive"
            ),
            Tool(
                name="get_sheet_data",
                func=self.sheets_service.get_sheet_data,
                description="Get data from a Google Sheet"
            ),
            Tool(
                name="get_directions",
                func=self.maps_service.get_directions,
                description="Get directions between two locations"
            )
        ]

        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "{input}\n\n{agent_scratchpad}")
        ])

        # Create the agent
        agent = create_openai_functions_agent(
            llm=ChatOpenAI(temperature=0),
            tools=tools,
            prompt=prompt
        )

        return agent

    async def process_messages(self, messages):
        """Process a list of messages and return a response."""
        if not self.agent:
            raise RuntimeError("Agent not initialized. Call async_init() first.")
            
        # Convert messages to the format expected by the agent
        input_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                if msg["role"] == "user":
                    input_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    input_messages.append(AIMessage(content=msg["content"]))
                elif msg["role"] == "system":
                    input_messages.append(SystemMessage(content=msg["content"]))
            else:
                input_messages.append(msg)

        # Process the messages
        response = await self.agent.ainvoke({"input": input_messages, "intermediate_steps": []})
        if hasattr(response, "return_values"):
            return response.return_values["output"]
        else:
            # Fallback for intermediate or action log responses
            return str(response)

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
                )
            ])
        logger.info(f"Created {len(tools)} tools for agent")
        return tools

    def _handle_calendar_operations(self, operation_json):
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
                return self.calendar_service.get_upcoming_events(max_results)
            
            elif action == "getForDate":
                date = operation_json.get("date")
                if not date:
                    return "Error: Missing 'date' for getForDate operation"
                return self.calendar_service.get_events_for_date(date)
            
            elif action == "create":
                event_details = {
                    "summary": operation_json.get("summary", "Workout"),
                    "start": {"dateTime": operation_json.get("start")},
                    "end": {"dateTime": operation_json.get("end")},
                    "description": operation_json.get("description", "General fitness workout."),
                    "location": operation_json.get("location", "Gym")
                }
                return self.calendar_service.write_event(event_details)
            
            elif action == "delete":
                event_id = operation_json.get("eventId")
                if not event_id:
                    return "Error: Missing 'eventId' for delete operation"
                return self.calendar_service.delete_event(event_id)
            
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
