import json
import logging
from typing import TypedDict, Optional
from pydantic import BaseModel, Field
import re

from backend.messages import TOOL_CLARIFICATION_MESSAGE

logger = logging.getLogger(__name__)

class FindNearbyWorkoutLocationsInput(BaseModel):
    lat: float = Field(..., description="Latitude of the location")
    lng: float = Field(..., description="Longitude of the location")
    radius: int = Field(5000, description="Search radius in meters (default 5000)")

class ToolCall(TypedDict):
    tool_name: str
    tool_args: dict

def create_tool_call(tool_name: str, tool_args: dict) -> ToolCall:
    """Create a tool call object."""
    return {
        "tool_name": tool_name,
        "tool_args": tool_args
    }

def parse_tool_call(content: str) -> Optional[ToolCall]:
    """Parse a tool call from the content string."""
    try:
        # Try to parse JSON format
        json_match = re.search(r'```(?:json)?\s*({[^}]+})\s*```', content)
        if json_match:
            tool_call = json.loads(json_match.group(1))
            if isinstance(tool_call, dict) and "tool_name" in tool_call and "tool_args" in tool_call:
                return tool_call
    except Exception:
        pass

    try:
        # Try to parse natural language format
        tool_match = re.search(r'(?:use|call|invoke|execute)\s+(\w+)(?:\s+with\s+args?)?\s*[:=]?\s*({[^}]+})', content, re.IGNORECASE)
        if tool_match:
            tool_name = tool_match.group(1)
            tool_args = json.loads(tool_match.group(2))
            return create_tool_call(tool_name, tool_args)
    except Exception:
        pass

    return None

class CalendarTool:
    """Handles all calendar operations through a single interface."""
    
    def __init__(self, calendar_service):
        self.calendar_service = calendar_service

    def handle_operations(self, operation_json):
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
            return f"Error handling calendar operation: {str(e)}"

class WorkoutTool:
    """Handles all workout-related operations through a single interface."""
    
    def __init__(self, calendar_service, gmail_service, tasks_service, drive_service, sheets_service, maps_service):
        self.calendar_service = calendar_service
        self.gmail_service = gmail_service
        self.tasks_service = tasks_service
        self.drive_service = drive_service
        self.sheets_service = sheets_service
        self.maps_service = maps_service

    def handle_operations(self, operation_json):
        """Handle all workout operations through a single interface."""
        logger.info(f"[WorkoutTool] Received operation: {operation_json}")
        
        # Parse operation JSON
        if not isinstance(operation_json, dict):
            try:
                operation_json = json.loads(operation_json)
            except Exception as e:
                logger.error(f"[WorkoutTool] Could not parse operation_json: {e}")
                return TOOL_CLARIFICATION_MESSAGE
        
        action = operation_json.get("action")
        if not action:
            return "Error: Missing 'action' in workout operation"
        
        try:
            if action == "suggest":
                user_input = operation_json.get("userInput")
                if not user_input:
                    return "Error: Missing 'userInput' for suggest operation"
                return self._suggest_workout(user_input)
            
            elif action == "track":
                workout_data = operation_json.get("workoutData")
                if not workout_data:
                    return "Error: Missing 'workoutData' for track operation"
                return self._track_workout(workout_data)
            
            elif action == "createPlan":
                plan_data = operation_json.get("planData")
                if not plan_data:
                    return "Error: Missing 'planData' for createPlan operation"
                return self._create_workout_plan(plan_data)
            
            elif action == "findLocations":
                location_data = operation_json.get("locationData")
                if not location_data:
                    return "Error: Missing 'locationData' for findLocations operation"
                return self._find_workout_locations(location_data)
            
            else:
                return f"Error: Unknown workout action '{action}'"
                
        except Exception as e:
            logger.error(f"[WorkoutTool] Error handling operation: {e}")
            return f"Error handling workout operation: {str(e)}"

    def _suggest_workout(self, user_input: str) -> str:
        """Suggest a workout based on user input."""
        logger.info(f"[WorkoutTool] Suggesting workout for input: {user_input}")
        try:
            # Get context from services
            events = self.calendar_service.get_upcoming_events()
            emails = self.gmail_service.get_recent_emails()
            tasks = self.tasks_service.get_workout_tasks("default")
            
            context = f"""
            Calendar Events: {events}
            Recent Emails: {emails}
            Workout Tasks: {tasks}
            """
            
            return f"Based on your input '{user_input}' and your current context:\n{context}\nHere's a suggested workout plan..."
            
        except Exception as e:
            logger.error(f"[WorkoutTool] Error suggesting workout: {e}")
            return f"Error suggesting workout: {str(e)}"

    def _track_workout(self, workout_data: dict) -> str:
        """Track a completed workout."""
        logger.info(f"[WorkoutTool] Tracking workout: {workout_data}")
        try:
            # Add workout entry to sheets
            self.sheets_service.add_workout_entry(
                spreadsheet_id=workout_data.get('spreadsheet_id'),
                date=workout_data.get('date'),
                workout_type=workout_data.get('type'),
                duration=workout_data.get('duration'),
                calories=workout_data.get('calories'),
                notes=workout_data.get('notes', '')
            )
            
            # Complete associated task if any
            if workout_data.get('task_id'):
                self.tasks_service.update_task(
                    tasklist_id=workout_data.get('tasklist_id'),
                    task_id=workout_data.get('task_id'),
                    status='completed'
                )
            
            return "Workout tracked successfully"
            
        except Exception as e:
            logger.error(f"[WorkoutTool] Error tracking workout: {e}")
            return f"Error tracking workout: {str(e)}"

    def _create_workout_plan(self, plan_data: dict) -> str:
        """Create a new workout plan."""
        logger.info(f"[WorkoutTool] Creating workout plan: {plan_data}")
        try:
            # Create folder for the plan
            folder = self.drive_service.create_folder(
                name=plan_data.get('name', 'Workout Plans')
            )
            
            # Create tasklist for the plan
            tasklist = self.tasks_service.create_workout_tasklist(
                title=plan_data.get('name', 'Workout Goals')
            )
            
            # Create spreadsheet for tracking
            spreadsheet = self.sheets_service.create_workout_tracker(
                title=plan_data.get('name', 'Workout Tracker')
            )
            
            return f"Workout plan created successfully:\nFolder: {folder}\nTasklist: {tasklist}\nTracker: {spreadsheet}"
            
        except Exception as e:
            logger.error(f"[WorkoutTool] Error creating workout plan: {e}")
            return f"Error creating workout plan: {str(e)}"

    def _find_workout_locations(self, location_data: dict) -> str:
        """Find nearby workout locations."""
        logger.info(f"[WorkoutTool] Finding workout locations: {location_data}")
        try:
            lat = location_data.get('lat')
            lng = location_data.get('lng')
            radius = location_data.get('radius', 5000)
            
            if not lat or not lng:
                return "Error: Missing latitude or longitude"
            
            locations = self.maps_service.find_nearby_workout_locations(
                lat=lat,
                lng=lng,
                radius=radius
            )
            
            return f"Found {len(locations)} workout locations near you:\n" + "\n".join(locations)
            
        except Exception as e:
            logger.error(f"[WorkoutTool] Error finding workout locations: {e}")
            return f"Error finding workout locations: {str(e)}"

class GoogleMaps:
    """Handles all Google Maps operations through a single interface."""
    
    def __init__(self, maps_service):
        self.maps_service = maps_service

    async def ainvoke(self, operation_json):
        """Handle all maps operations through a single interface asynchronously."""
        logger.info(f"[GoogleMaps] Received operation: {operation_json}")
        
        # Parse operation JSON
        if not isinstance(operation_json, dict):
            try:
                operation_json = json.loads(operation_json)
            except Exception as e:
                logger.error(f"[GoogleMaps] Could not parse operation_json: {e}")
                return "I couldn't understand the request format. Please provide a valid JSON object with 'action' and required parameters."

        action = operation_json.get("action")
        if not action:
            return "Please specify an action (e.g., 'search_places', 'get_directions', 'get_place_details')"
        
        try:
            if action == "search_places":
                query = operation_json.get("query")
                location = operation_json.get("location")
                radius = operation_json.get("radius", 5000)
                max_results = operation_json.get("max_results", 10)
                
                if not query:
                    return "Please specify what type of places you're looking for (e.g., 'gym', 'fitness center')"
                if not location:
                    return "Please provide a location to search around"
                
                # If location is an address string, geocode it first
                if isinstance(location, str):
                    try:
                        geocode_result = await self.maps_service.geocode_address(location)
                        if not geocode_result:
                            return f"I couldn't find the location: {location}. Please check the address and try again."
                        location = geocode_result
                    except ValueError as e:
                        return str(e)
                
                # Search for places
                try:
                    places = await self.maps_service.search_places(
                        query=query,
                        location=location,
                        radius=radius,
                        max_results=max_results
                    )
                    
                    if not places:
                        return f"I couldn't find any {query} locations near {location}"
                    
                    # Format the response
                    response = f"I found {len(places)} {query} locations near you:\n\n"
                    for i, place in enumerate(places, 1):
                        response += f"{i}. {place['name']}\n"
                        response += f"   Address: {place['address']}\n"
                        if place['rating'] != 'No rating':
                            response += f"   Rating: {place['rating']}/5.0\n"
                        if place.get('types'):
                            response += f"   Types: {', '.join(place['types'])}\n"
                        response += "\n"
                    
                    return response
                    
                except ValueError as e:
                    return str(e)
            
            elif action == "find_workout_locations":
                address = operation_json.get("address")
                radius = operation_json.get("radius", 5000)
                max_results = operation_json.get("max_results", 10)
                
                if not address:
                    return "Please provide an address to search around"
                
                try:
                    # First geocode the address
                    geocode_result = await self.maps_service.geocode_address(address)
                    if not geocode_result:
                        return f"I couldn't find the location: {address}. Please check the address and try again."
                    
                    # Then search for gyms and fitness centers
                    places = await self.maps_service.search_places(
                        query="gym OR fitness center",
                        location=geocode_result,
                        radius=radius,
                        max_results=max_results
                    )
                    
                    if not places:
                        return f"I couldn't find any gyms or fitness centers near {address}"
                    
                    # Format the response
                    response = f"I found {len(places)} workout locations near {address}:\n\n"
                    for i, place in enumerate(places, 1):
                        response += f"{i}. {place['name']}\n"
                        response += f"   Address: {place['address']}\n"
                        if place['rating'] != 'No rating':
                            response += f"   Rating: {place['rating']}/5.0\n"
                        if place.get('types'):
                            response += f"   Types: {', '.join(place['types'])}\n"
                        response += "\n"
                    
                    return response
                    
                except ValueError as e:
                    return str(e)
            
            elif action == "get_directions":
                origin = operation_json.get("origin")
                destination = operation_json.get("destination")
                mode = operation_json.get("mode", "driving")
                
                if not origin or not destination:
                    return "Please provide both origin and destination locations"
                
                try:
                    directions = await self.maps_service.get_directions(
                        origin=origin,
                        destination=destination,
                        mode=mode
                    )
                    
                    if not directions:
                        return f"I couldn't find directions from {origin} to {destination}"
                    
                    # Format the response
                    response = f"Here are the directions from {origin} to {destination}:\n\n"
                    for i, step in enumerate(directions[0]['legs'][0]['steps'], 1):
                        response += f"{i}. {step['html_instructions']}\n"
                        response += f"   Distance: {step['distance']['text']}\n"
                        response += f"   Duration: {step['duration']['text']}\n\n"
                    
                    return response
                    
                except ValueError as e:
                    return str(e)
            
            elif action == "get_place_details":
                place_id = operation_json.get("place_id")
                
                if not place_id:
                    return "Please provide a place ID to get details for"
                
                try:
                    details = await self.maps_service.get_place_details(place_id)
                    
                    if not details:
                        return f"I couldn't find details for the specified place"
                    
                    # Format the response
                    response = f"Here are the details for {details.get('name', 'Unknown Place')}:\n\n"
                    if details.get('formatted_address'):
                        response += f"Address: {details['formatted_address']}\n"
                    if details.get('formatted_phone_number'):
                        response += f"Phone: {details['formatted_phone_number']}\n"
                    if details.get('rating'):
                        response += f"Rating: {details['rating']}/5.0\n"
                    if details.get('opening_hours'):
                        response += f"Open Now: {'Yes' if details['opening_hours'].get('open_now') else 'No'}\n"
                    if details.get('website'):
                        response += f"Website: {details['website']}\n"
                    
                    return response
                    
                except ValueError as e:
                    return str(e)
            
            else:
                return f"I don't understand the action '{action}'. Please use one of: search_places, find_workout_locations, get_directions, get_place_details"
                
        except Exception as e:
            logger.error(f"[GoogleMaps] Error handling operation: {e}")
            return f"I encountered an error while processing your request: {str(e)}"

class DriveTool:
    def __init__(self, drive_service):
        self.drive_service = drive_service
    def handle_operations(self, operation_json):
        # For now, just a placeholder for integration test import
        return "DriveTool operation handled"

class GmailTool:
    def __init__(self, gmail_service):
        self.gmail_service = gmail_service
    def handle_operations(self, operation_json):
        return "GmailTool operation handled"

def create_tools(calendar_service=None, gmail_service=None, tasks_service=None, drive_service=None, sheets_service=None, maps_service=None):
    """Create the tools for the agent."""
    logger.debug("Creating tools for agent...")
    tools = []
    
    if maps_service:
        maps_tool = GoogleMaps(maps_service)
        tools.append(StructuredTool(
            name="GoogleMaps",
            description="""Handle all Google Maps operations. Input should be a JSON object with:
            - action: One of 'search_places', 'find_workout_locations', 'get_directions', 'get_place_details'
            For finding workout locations:
            - action: 'find_workout_locations'
            - address: The address to search around
            - radius: Optional search radius in meters (default 5000)
            - max_results: Optional maximum number of results (default 10)
            Example: {\"action\": \"find_workout_locations\", \"address\": \"123 Main St, New York, NY\", \"radius\": 5000}
            For general place search:
            - action: 'search_places'
            - query: The type of place to search for
            - location: Either coordinates {'lat': float, 'lng': float} or an address string
            - radius: Optional search radius in meters (default 5000)
            Example: {\"action\": \"search_places\", \"query\": \"gym\", \"location\": \"123 Main St, New York, NY\"}""",
            coroutine=lambda **kwargs: maps_tool.ainvoke(kwargs),
            args_schema=None
        ))
    
    if calendar_service:
        calendar_tool = CalendarTool(calendar_service)
        tools.append(Tool(
            name="GoogleCalendar",
            func=calendar_tool.handle_operations,
            description="""Handle all calendar operations. Input should be a JSON object with:
            - action: One of 'getUpcoming', 'getForDate', 'create', 'delete'
            - For getUpcoming: Optional maxResults (default 10)
            - For getForDate: date (YYYY-MM-DD or natural language like 'today', 'tomorrow')
            - For create: summary, start, end, description, location
            - For delete: eventId
            Example: {\"action\": \"getForDate\", \"date\": \"tomorrow\"}"""
        ))
    
    if gmail_service:
        logger.debug("Adding Gmail tools...")
        tools.append(Tool(
            name="Email",
            func=gmail_service.get_recent_emails,
            description="Get recent emails"
        ))
    
    if tasks_service:
        logger.debug("Adding Tasks tools...")
        tools.extend([
            Tool(
                name="CreateWorkoutTaskList",
                func=tasks_service.create_workout_tasklist,
                description="Create a new task list for workout goals"
            ),
            Tool(
                name="AddWorkoutTask",
                func=tasks_service.add_workout_task,
                description="Add a new workout task"
            ),
            Tool(
                name="GetWorkoutTasks",
                func=tasks_service.get_workout_tasks,
                description="Get all workout tasks"
            )
        ])
    
    if drive_service:
        logger.debug("Adding Drive tools...")
        tools.extend([
            Tool(
                name="CreateWorkoutFolder",
                func=drive_service.create_folder,
                description="Create a folder for workout plans"
            ),
            Tool(
                name="UploadWorkoutPlan",
                func=drive_service.upload_file,
                description="Upload a workout plan"
            )
        ])
    
    if sheets_service:
        logger.debug("Adding Sheets tools...")
        tools.extend([
            Tool(
                name="CreateWorkoutTracker",
                func=sheets_service.create_workout_tracker,
                description="Create a new workout tracker spreadsheet"
            ),
            Tool(
                name="AddWorkoutEntry",
                func=sheets_service.add_workout_entry,
                description="Add a workout entry to the tracker"
            ),
            Tool(
                name="AddNutritionEntry",
                func=sheets_service.add_nutrition_entry,
                description="Add a nutrition entry to the tracker"
            )
        ])
    
    logger.info(f"Created {len(tools)} tools for agent")
    return tools 

# Export for import in tests
__all__ = [
    "GoogleMaps",
    "CalendarTool",
    "DriveTool",
    "GmailTool"
] 