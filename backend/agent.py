from langchain_core.tools import Tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing import List, Union, Dict, Any, Optional, TypedDict, Annotated, Sequence
import re
from datetime import datetime, timedelta
from backend.google_services.calendar import GoogleCalendarService
from backend.google_services.gmail import GoogleGmailService
from backend.google_services.fit import GoogleFitnessService
from backend.google_services.tasks import GoogleTasksService
from backend.google_services.drive import GoogleDriveService
from backend.google_services.sheets import GoogleSheetsService
from backend.google_services.maps import GoogleMapsService
import os
from dotenv import load_dotenv
import logging
import uuid
import json
from langchain.prompts import ChatPromptTemplate
from backend.agent_state import AgentState
from backend.prompts import AGENT_TOOL_PROMPT, AGENT_PERSONAL_TRAINER_FULL_GUIDELINES_PROMPT
from backend.messages import TOOL_CLARIFICATION_MESSAGE, TOOL_TIME_ERROR_MESSAGE
import traceback
from pydantic.v1 import BaseModel, Field
from langchain_core.tools import tool
import asyncio
import ast

load_dotenv()
logger = logging.getLogger(__name__)

class FindNearbyWorkoutLocationsInput(BaseModel):
    lat: float = Field(..., description="Latitude of the location")
    lng: float = Field(..., description="Longitude of the location")
    radius: int = Field(5000, description="Search radius in meters (default 5000)")

class PersonalTrainerAgent:
    """
    An AI-powered personal trainer agent that integrates with various Google services
    to provide personalized workout recommendations and tracking.
    """
    def __init__(self, calendar_service, gmail_service, tasks_service, drive_service, sheets_service, maps_service, llm=None):
        logger.info("Initializing PersonalTrainerAgent...")
        self.calendar_service = calendar_service
        self.gmail_service = gmail_service
        self.tasks_service = tasks_service
        self.drive_service = drive_service
        self.sheets_service = sheets_service
        self.maps_service = maps_service
        logger.debug("Initializing ChatOpenAI model...")
        self.llm = llm if llm is not None else ChatOpenAI(temperature=0, model="gpt-4")
        logger.debug("Creating tools...")
        self.tools = self._create_tools()
        self.tomorrow_date = self._get_tomorrow_date()
        logger.debug("Creating agent...")
        try:
            self.agent = asyncio.run(self._create_agent_workflow())
        except Exception as e:
            logger.error(f"Error creating agent: {e}")
            raise
        logger.info("PersonalTrainerAgent initialized successfully")
        self._state_lock = asyncio.Lock()
        self._workflow_lock = asyncio.Lock()

    def _create_tools(self):
        """Create the tools for the agent."""
        logger.debug("Creating tools for agent...")
        tools = [
            Tool(
                name="GoogleCalendar",
                func=self._handle_calendar_operations,
                description="""Handle all calendar operations. Input should be a JSON object with:
                - action: One of 'getUpcoming', 'getForDate', 'create', 'delete'
                - For getUpcoming: Optional maxResults (default 10)
                - For getForDate: date (YYYY-MM-DD or natural language like 'today', 'tomorrow')
                - For create: summary, start, end, description, location
                - For delete: eventId
                Example: {"action": "getForDate", "date": "tomorrow"}"""
            )
        ]
        
        # Add non-calendar tools only if the corresponding service is available
        if self.gmail_service:
            logger.debug("Adding Gmail tools...")
            tools.append(Tool(
                name="Email",
                func=self.gmail_service.get_recent_emails,
                description="Get recent emails"
            ))
        if self.tasks_service:
            logger.debug("Adding Tasks tools...")
            tools.extend([
                Tool(
                    name="CreateWorkoutTaskList",
                    func=self.tasks_service.create_workout_tasklist,
                    description="Create a new task list for workout goals"
                ),
                Tool(
                    name="AddWorkoutTask",
                    func=self.tasks_service.add_workout_task,
                    description="Add a new workout task"
                ),
                Tool(
                    name="GetWorkoutTasks",
                    func=self.tasks_service.get_workout_tasks,
                    description="Get all workout tasks"
                )
            ])
        if self.drive_service:
            logger.debug("Adding Drive tools...")
            tools.extend([
                Tool(
                    name="CreateWorkoutFolder",
                    func=self.drive_service.create_folder,
                    description="Create a folder for workout plans"
                ),
                Tool(
                    name="UploadWorkoutPlan",
                    func=self.drive_service.upload_file,
                    description="Upload a workout plan"
                )
            ])
        if self.sheets_service:
            logger.debug("Adding Sheets tools...")
            tools.extend([
                Tool(
                    name="CreateWorkoutTracker",
                    func=self.sheets_service.create_workout_tracker,
                    description="Create a new workout tracker spreadsheet"
                ),
                Tool(
                    name="AddWorkoutEntry",
                    func=self.sheets_service.add_workout_entry,
                    description="Add a workout entry to the tracker"
                ),
                Tool(
                    name="AddNutritionEntry",
                    func=self.sheets_service.add_nutrition_entry,
                    description="Add a nutrition entry to the tracker"
                )
            ])
        if self.maps_service:
            logger.debug("Adding Maps tools...")
            tools.extend([
                Tool(
                    name="GoogleMaps",
                    func=self.maps_service.search_places,
                    description="Search for places, get directions, and find locations using Google Maps"
                )
            ])
        logger.info(f"Created {len(tools)} tools for agent")
        return tools

    def _handle_calendar_operations(self, operation_json):
        """Handle all calendar operations through a single interface."""
        logger.info(f"[GoogleCalendar] Received operation: {operation_json}")
        
        # Parse operation JSON
        if not isinstance(operation_json, dict):
            try:
                operation_json = json.loads(operation_json)
            except Exception as e:
                logger.error(f"[GoogleCalendar] Could not parse operation_json: {e}")
                return TOOL_CLARIFICATION_MESSAGE
        
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

    def _extract_natural_language(self, content: str) -> str:
        """Extract only the natural language part before any tool call syntax."""
        # Remove everything after 'Tool Call:' or similar tool call syntax
        match = re.split(r'\n*Tool Call:.*', content, flags=re.IGNORECASE)
        return match[0].strip() if match else content

    async def process_messages(self, messages: List[Any]) -> str:
        """Process a list of messages and return the agent's response."""
        logger.info(f"[process_messages] Starting with {len(messages)} messages")
        max_iterations = 100
        try:
            async with self._state_lock:
                logger.info("[process_messages] Acquired state lock")
                async with self._workflow_lock:
                    logger.info("[process_messages] Acquired workflow lock")
                    if not hasattr(self, '_workflow'):
                        logger.info("[process_messages] Creating new workflow")
                        self._workflow = await self._create_agent_workflow()
                        logger.info("[process_messages] Workflow created")
                    
                    state = AgentState(
                        messages=messages,
                        status="active",
                        missing_fields=[],
                        last_tool_result=None
                    )
                    logger.info(f"[process_messages] Initial state created: {state}")
                    
                    for i in range(max_iterations):
                        logger.info(f"[process_messages] Starting iteration {i+1}/{max_iterations}")
                        result = await self._workflow.ainvoke(state.to_dict())
                        logger.info(f"[process_messages] Workflow result: {result}")
                        
                        if isinstance(result, dict) and "messages" in result:
                            final_messages = result["messages"]
                            logger.info(f"[process_messages] Final messages: {final_messages}")
                            
                            if final_messages and isinstance(final_messages[-1], AIMessage):
                                logger.info(f"[process_messages] Last message content: {final_messages[-1].content}")
                                # Check for terminal status
                                if result.get("status") in ("done", "error"):
                                    logger.info(f"[process_messages] Terminal status reached: {result.get('status')}")
                                    # POST-PROCESSING: Filter out tool call syntax in the final response
                                    content = final_messages[-1].content
                                    # If the content looks like a tool call, skip it and look for the last natural language message
                                    import re
                                    tool_call_pattern = re.compile(r"^Tool Call: ", re.IGNORECASE)
                                    if tool_call_pattern.match(content):
                                        # Find the last AIMessage that does not look like a tool call
                                        for msg in reversed(final_messages):
                                            if isinstance(msg, AIMessage) and not tool_call_pattern.match(msg.content):
                                                logger.info(f"[process_messages] Returning last natural language AIMessage: {msg.content}")
                                                return msg.content
                                        # If all AI messages are tool calls, return a generic confirmation
                                        logger.info("[process_messages] All AI messages are tool calls, returning generic confirmation.")
                                        return "I've completed your request."
                                    return content
                                # Otherwise, update state and continue
                                logger.info(f"[process_messages] Updating state for next iteration")
                                state = AgentState.from_dict(result)
                        else:
                            logger.warning(f"[process_messages] Invalid result format: {result}")
                            break
                    
                    logger.error(f"[process_messages] Max iterations ({max_iterations}) reached without reaching a terminal state")
                    return "I apologize, but I couldn't process your request due to an internal loop. Please try again."
        except Exception as e:
            logger.error(f"[process_messages] Error processing messages: {str(e)}", exc_info=True)
            return f"I apologize, but I encountered an error: {str(e)}"

    def suggest_workout(self, user_input: str) -> str:
        """
        Suggest a workout based on user input and available data.
        
        Args:
            user_input: The user's workout request or requirements
            
        Returns:
            str: A personalized workout suggestion
        """
        try:
            logger.info(f"Suggesting workout for input: {user_input}")
            context = self._get_context()
            full_input = f"""Context: {context}
User Input: {user_input}
Please suggest a workout plan based on the above context and user input."""
            
            logger.debug("Invoking LLM for workout suggestion...")
            response = self.agent.invoke(full_input)
            logger.info("Successfully generated workout suggestion")
            return response
        except Exception as e:
            logger.error(f"Error suggesting workout: {str(e)}", exc_info=True)
            return f"Error suggesting workout: {str(e)}"

    def _get_context(self) -> str:
        """
        Gather relevant context from all services.
        
        Returns:
            str: A string containing all relevant context for workout suggestions
        """
        try:
            logger.debug("Gathering context from services...")
            events = self.calendar_service.get_upcoming_events()
            emails = self.gmail_service.get_recent_emails()
            tasks = self.tasks_service.get_workout_tasks("default")
            
            context = f"""
Calendar Events: {events}
Recent Emails: {emails}
Workout Tasks: {tasks}
"""
            logger.debug("Successfully gathered context")
            return context
        except Exception as e:
            logger.error(f"Error gathering context: {str(e)}", exc_info=True)
            return f"Error gathering context: {str(e)}"

    def track_workout(self, workout_data: Dict[str, Any]) -> str:
        """
        Track a completed workout across various services.
        
        Args:
            workout_data: Dictionary containing workout details
            
        Returns:
            str: Success or error message
        """
        try:
            logger.info(f"Tracking workout: {workout_data}")
            self.sheets_service.add_workout_entry(
                spreadsheet_id=workout_data.get('spreadsheet_id'),
                date=workout_data.get('date'),
                workout_type=workout_data.get('type'),
                duration=workout_data.get('duration'),
                calories=workout_data.get('calories'),
                notes=workout_data.get('notes', '')
            )
            
            if workout_data.get('task_id'):
                logger.debug("Completing associated workout task...")
                self.tasks_service.complete_workout_task(
                    tasklist_id=workout_data.get('tasklist_id'),
                    task_id=workout_data.get('task_id')
                )
            
            logger.info("Successfully tracked workout")
            return "Workout tracked successfully"
        except Exception as e:
            logger.error(f"Error tracking workout: {str(e)}", exc_info=True)
            return f"Error tracking workout: {str(e)}"

    def create_workout_plan(self, plan_data: Dict[str, Any]) -> str:
        """
        Create and store a workout plan across various services.
        
        Args:
            plan_data: Dictionary containing workout plan details
            
        Returns:
            str: Success or error message
        """
        try:
            logger.info(f"Creating workout plan: {plan_data}")
            folder = self.drive_service.create_folder(
                name=plan_data.get('name', 'Workout Plans')
            )
            
            tasklist = self.tasks_service.create_workout_tasklist(
                title=plan_data.get('name', 'Workout Goals')
            )
            
            spreadsheet = self.sheets_service.create_workout_tracker(
                title=plan_data.get('name', 'Workout Tracker')
            )
            
            logger.info("Successfully created workout plan")
            return f"Workout plan created successfully:\nFolder: {folder}\nTasklist: {tasklist}\nTracker: {spreadsheet}"
        except Exception as e:
            logger.error(f"Error creating workout plan: {str(e)}", exc_info=True)
            return f"Error creating workout plan: {str(e)}"

    def _get_tomorrow_date(self):
        """Get tomorrow's date in ISO format."""
        tomorrow = datetime.now() + timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d")

    async def _create_agent_workflow(self):
        """Create an async workflow with proper state management."""
        logger.info("[_create_agent_workflow] Starting workflow creation")
        
        def ensure_agent_state(state):
            logger.info(f"[ensure_agent_state] Converting state: {state}")
            if isinstance(state, AgentState):
                return state
            elif isinstance(state, dict):
                return AgentState.from_dict(state)
            else:
                raise ValueError(f"Invalid state type: {type(state)}")

        async def end_node(state):
            logger.info("[end_node] Starting end node")
            state = ensure_agent_state(state)
            logger.info(f"[end_node] State before processing: {state}")
            
            if not state.messages:
                logger.error("[end_node] No messages in state")
                state = AgentState(
                    messages=[AIMessage(content="I apologize, but I couldn't process your request. Please try again.")],
                    status="error"
                )
            else:
                state = AgentState(
                    messages=state.messages,
                    status="done",
                    missing_fields=state.missing_fields,
                    last_tool_result=state.last_tool_result
                )
            logger.info(f"[end_node] Final state: {state}")
            return state.to_dict()

        async def agent_node(state):
            logger.info("[agent_node] Starting agent node")
            state = ensure_agent_state(state)
            logger.info(f"[agent_node] State before processing: {state}")
            
            messages = state.messages
            if not messages:
                logger.error("[agent_node] No messages in state")
                state = AgentState(
                    messages=[AIMessage(content="I apologize, but I couldn't process your request. Please try again.")],
                    status="error"
                )
                return state.to_dict()
            
            try:
                # If we have a tool result, generate a post-tool-call confirmation
                if state.last_tool_result is not None:
                    logger.info("[agent_node] Processing last_tool_result for post-tool-call confirmation")
                    # Add the tool result as a message for the LLM to see
                    tool_result_message = AIMessage(content=f"[TOOL RESULT]: {state.last_tool_result}")
                    # Add a system message to instruct the LLM
                    system_message = SystemMessage(content="You have just completed a tool action. Now, confirm the outcome to the user in natural language, including any relevant details from the tool result.")
                    llm_messages = [system_message] + messages + [tool_result_message]
                    response = await self.llm.ainvoke(llm_messages)
                    logger.info(f"[agent_node] LLM follow-up response received: {response}")
                    response_nl = AIMessage(content=response.content)
                    state = AgentState(
                        messages=messages + [tool_result_message, response_nl],
                        status="done",
                        missing_fields=state.missing_fields,
                        last_tool_result=None
                    )
                    logger.info(f"[agent_node] Final state after confirmation: {state}")
                    return state.to_dict()
                
                system_message = SystemMessage(content=AGENT_PERSONAL_TRAINER_FULL_GUIDELINES_PROMPT)
                llm_messages = [system_message] + messages
                logger.info(f"[agent_node] Calling LLM with {len(llm_messages)} messages")
                logger.debug(f"[agent_node] LLM messages: {llm_messages}")
                
                response = await self.llm.ainvoke(llm_messages)
                logger.info(f"[agent_node] LLM response received: {response}")
                logger.debug(f"[agent_node] LLM response type: {type(response)}")
                logger.debug(f"[agent_node] LLM response content: {response.content}")
                logger.debug(f"[agent_node] LLM response additional_kwargs: {getattr(response, 'additional_kwargs', {})}")
                
                tool_calls = response.additional_kwargs.get("tool_calls", [])
                logger.info(f"[agent_node] Tool calls found: {tool_calls}")
                
                # Only add the natural language part to messages
                nl_content = self._extract_natural_language(response.content)
                response_nl = AIMessage(content=nl_content)
                
                # Detect tool call syntax in content if tool_calls is empty
                has_tool_call_syntax = "Tool Call:" in response.content
                if tool_calls or has_tool_call_syntax:
                    logger.info("[agent_node] Detected tool call (structured or syntax), setting status to awaiting_tool")
                    state = AgentState(
                        messages=messages + [response_nl],
                        status="awaiting_tool",
                        missing_fields=state.missing_fields,
                        last_tool_result=None
                    )
                else:
                    logger.info("[agent_node] No tool calls, setting status to done")
                    state = AgentState(
                        messages=messages + [response_nl],
                        status="done",
                        missing_fields=state.missing_fields,
                        last_tool_result=None
                    )
                logger.info(f"[agent_node] Final state: {state}")
                return state.to_dict()
            except Exception as e:
                logger.error(f"[agent_node] Error: {e}", exc_info=True)
                state = AgentState(
                    messages=messages + [AIMessage(content=f"I apologize, but I encountered an error: {str(e)}")],
                    status="error"
                )
                return state.to_dict()

        async def tool_node(state):
            logger.info("[tool_node] Starting tool node")
            state = ensure_agent_state(state)
            logger.info(f"[tool_node] State before processing: {state}")
            
            messages = state.messages
            if not messages:
                logger.error("[tool_node] No messages in state")
                state = AgentState(
                    messages=[AIMessage(content="I apologize, but I couldn't process your request. Please try again.")],
                    status="error"
                )
                return state.to_dict()
            
            try:
                last_message = messages[-1]
                tool_calls = getattr(last_message, 'additional_kwargs', {}).get("tool_calls", [])
                logger.info(f"[tool_node] Tool calls found: {tool_calls}")
                
                # If no structured tool_calls, try to parse from content
                if not tool_calls:
                    import re
                    import ast
                    content = getattr(last_message, 'content', '')
                    # Find all tool calls in the message, even with newlines or extra text
                    matches = re.findall(r'Tool Call:\s*(\w+)\((.*?)\)', content, re.DOTALL | re.IGNORECASE)
                    if matches:
                        tool_name, args_str = matches[0]
                        tool_args = {}
                        arg_pairs = re.findall(r'(\w+)\s*=\s*({.*?}|\".*?\"|\'.*?\'|[^,]+)', args_str)
                        for k, v in arg_pairs:
                            v = v.strip()
                            if v.startswith('{') and v.endswith('}'):
                                try:
                                    tool_args[k] = ast.literal_eval(v)
                                except Exception:
                                    try:
                                        tool_args[k] = json.loads(v)
                                    except Exception:
                                        tool_args[k] = v
                            elif (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                                tool_args[k] = v[1:-1]
                            else:
                                tool_args[k] = v
                        tool_calls = [{
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(tool_args)
                            }
                        }]
                        logger.info(f"[tool_node] Parsed tool call from content: {tool_calls}")
                
                if not tool_calls:
                    logger.info("[tool_node] No tool calls, setting status to done")
                    state = AgentState(
                        messages=messages,
                        status="done",
                        missing_fields=state.missing_fields,
                        last_tool_result=state.last_tool_result
                    )
                    return state.to_dict()
                
                tool_call = tool_calls[0]
                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])
                logger.info(f"[tool_node] Executing tool: {tool_name} with args: {tool_args}")
                
                tool = next((t for t in self.tools if t.name == tool_name), None)
                if not tool:
                    logger.error(f"[tool_node] Tool {tool_name} not found")
                    state = AgentState(
                        messages=messages + [AIMessage(content=f"I apologize, but I couldn't find the tool {tool_name}.")],
                        status="error"
                    )
                    return state.to_dict()
                
                try:
                    logger.info(f"[tool_node] Invoking tool {tool_name}")
                    result = await tool.ainvoke(tool_args)
                    logger.info(f"[tool_node] Tool {tool_name} executed successfully")
                    
                    # After tool execution, set status to active to allow the agent to process the result
                    state = AgentState(
                        messages=messages,
                        status="active",
                        missing_fields=state.missing_fields,
                        last_tool_result=result
                    )
                    logger.info(f"[tool_node] Final state: {state}")
                    return state.to_dict()
                except Exception as e:
                    logger.error(f"[tool_node] Error executing tool {tool_name}: {e}")
                    state = AgentState(
                        messages=messages + [AIMessage(content=f"I apologize, but I encountered an error while using {tool_name}: {str(e)}")],
                        status="error"
                    )
                    return state.to_dict()
            except Exception as e:
                logger.error(f"[tool_node] Error: {e}")
                state = AgentState(
                    messages=messages + [AIMessage(content=f"I apologize, but I encountered an error: {str(e)}")],
                    status="error"
                )
                return state.to_dict()

        # Create the graph
        logger.info("[_create_agent_workflow] Creating workflow graph")
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("agent", agent_node)
        workflow.add_node("tool", tool_node)
        workflow.add_node("end", end_node)
        
        # Define router functions
        def agent_router(state):
            if state.status == "awaiting_tool":
                return "tool"
            elif state.status == "active" and state.last_tool_result is not None:
                return "agent"
            return "end"
            
        def tool_router(state):
            if state.status == "active":
                return "agent"
            elif state.status == "awaiting_tool":
                return "tool"
            return "end"
        
        # Add edges
        workflow.add_conditional_edges("agent", agent_router)
        workflow.add_conditional_edges("tool", tool_router)
        
        # Set entry point
        workflow.set_entry_point("agent")
        logger.info("[_create_agent_workflow] Workflow graph created")
        
        return workflow.compile()
