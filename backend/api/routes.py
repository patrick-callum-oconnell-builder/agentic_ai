import logging
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.agent import PersonalTrainerAgent
from backend.google_services.calendar import GoogleCalendarService
from backend.google_services.gmail import GoogleGmailService
from backend.google_services.maps import GoogleMapsService
from backend.google_services.fit import GoogleFitnessService
from backend.google_services.tasks import GoogleTasksService
from backend.google_services.drive import GoogleDriveService
from backend.google_services.sheets import GoogleSheetsService
import os
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pydantic import validator
import asyncio

# Configure logger
logger = logging.getLogger(__name__)

router = APIRouter()

# Global service instances
calendar_service = None
gmail_service = None
maps_service = None
fitness_service = None
tasks_service = None
drive_service = None
sheets_service = None
_agent = None

async def initialize_services():
    """Initialize all Google services asynchronously."""
    global calendar_service, gmail_service, maps_service, fitness_service, tasks_service, drive_service, sheets_service
    try:
        logger.info("Initializing Google services...")
        calendar_service = GoogleCalendarService()
        gmail_service = GoogleGmailService()
        maps_service = GoogleMapsService()
        fitness_service = GoogleFitnessService()
        tasks_service = GoogleTasksService()
        drive_service = GoogleDriveService()
        sheets_service = GoogleSheetsService()
        logger.info("All Google services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise RuntimeError(f"Failed to initialize services: {str(e)}")

async def get_agent():
    """Get or create an agent instance."""
    global _agent
    if not _agent:
        _agent = PersonalTrainerAgent(
            calendar_service=calendar_service,
            gmail_service=gmail_service,
            tasks_service=tasks_service,
            drive_service=drive_service,
            sheets_service=sheets_service,
            maps_service=maps_service
        )
        await _agent.async_init()
    return _agent

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.debug("Health check endpoint called")
    if not all([calendar_service, gmail_service, maps_service, fitness_service, tasks_service, drive_service, sheets_service]):
        raise HTTPException(status_code=503, detail="Services not initialized")
    return {"status": "healthy"}

@router.post("/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks, x_api_key: Optional[str] = Header(None)):
    try:
        logger.info(f"Chat endpoint called with {len(request.messages)} messages")
        # Convert Pydantic Message objects to dicts
        raw_messages = [msg.dict() if hasattr(msg, 'dict') else msg for msg in request.messages]
        logger.debug(f"Raw incoming messages: {raw_messages}")
        # Normalize messages
        normalized_messages = []
        for i, msg in enumerate(raw_messages):
            if not isinstance(msg, dict):
                logger.error(f"Message {i} is not a dict: {msg}")
                continue
            if 'role' not in msg or 'content' not in msg:
                logger.error(f"Message {i} missing required fields: {msg}")
                continue
            role = msg['role']
            content = msg['content']
            if role not in {"user", "assistant", "system"}:
                logger.error(f"Message {i} has invalid role: {role}")
                continue
            normalized = {"role": role, "content": content.strip()}
            logger.debug(f"Successfully normalized message {i}: {msg} -> {normalized}")
            normalized_messages.append(normalized)
        logger.debug(f"Normalized messages to be processed: {normalized_messages}")

        if not normalized_messages:
            logger.error("No valid messages after normalization")
            raise HTTPException(status_code=400, detail="No valid messages to process")

        # Get the agent and process messages
        agent = await get_agent()
        response = await agent.process_messages(normalized_messages)
        logger.info("Successfully processed messages")
        return {"response": response}
    except Exception as e:
        import traceback
        logger.error(f"Error in /chat endpoint: {str(e)}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")
        for handler in logger.handlers:
            handler.flush()
        with open("backend_error.log", "a") as f:
            f.write("TOP-LEVEL ERROR:\n" + traceback.format_exc() + "\n")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/calendar/events")
async def get_calendar_events():
    """Get upcoming calendar events."""
    logger.info("Calendar events endpoint called")
    try:
        events = calendar_service.get_upcoming_events()
        logger.info(f"Retrieved {len(events)} calendar events")
        return {"events": events}
    except Exception as e:
        logger.error(f"Error retrieving calendar events: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gmail/recent")
async def get_recent_emails():
    """Get recent emails."""
    logger.info("Recent emails endpoint called")
    try:
        emails = gmail_service.get_recent_emails()
        logger.info(f"Retrieved {len(emails)} recent emails")
        return {"emails": emails}
    except Exception as e:
        logger.error(f"Error retrieving recent emails: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/maps/nearby")
async def get_nearby_locations():
    """Get nearby workout locations."""
    logger.info("Nearby locations endpoint called")
    try:
        locations = maps_service.find_nearby_workout_locations()
        logger.info(f"Retrieved {len(locations)} nearby locations")
        return {"locations": locations}
    except Exception as e:
        logger.error(f"Error retrieving nearby locations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fitness/activities")
async def get_fitness_activities():
    """Get fitness activities."""
    logger.info("Fitness activities endpoint called")
    try:
        activities = fitness_service.get_activities()
        logger.info(f"Retrieved {len(activities)} fitness activities")
        return {"activities": activities}
    except Exception as e:
        logger.error(f"Error retrieving fitness activities: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks")
async def get_tasks():
    """Get tasks."""
    logger.info("Tasks endpoint called")
    try:
        tasks = tasks_service.get_tasks()
        logger.info(f"Retrieved {len(tasks)} tasks")
        return {"tasks": tasks}
    except Exception as e:
        logger.error(f"Error retrieving tasks: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/shutdown")
async def shutdown(request: Request):
    """Shutdown endpoint."""
    logger.info("Shutdown endpoint called")
    try:
        # Write a shutdown signal file
        with open("shutdown.signal", "w") as f:
            f.write("shutdown")
        logger.info("Shutdown signal file created")
        return JSONResponse({"message": "Shutting down servers..."})
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 