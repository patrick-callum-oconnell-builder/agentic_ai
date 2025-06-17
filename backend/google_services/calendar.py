from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import List, Dict, Optional, Any
from pytz import timezone
import dateparser
import logging
from backend.google_services.base import GoogleServiceBase
from backend.google_services.auth import get_google_credentials
import asyncio

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.pickle.
class GoogleCalendarService(GoogleServiceBase):
    """Service for interacting with Google Calendar API."""
    
    def __init__(self):
        """Initialize the Calendar service."""
        self.SCOPES = ['https://www.googleapis.com/auth/calendar']
        super().__init__()
        # Note: initialize_service() is now async, but __init__ cannot be async
        # We'll handle initialization in initialize_service instead
        self.user_tz = timezone('America/Los_Angeles')

    async def initialize_service(self):
        """Initialize the Google Calendar service using the new OAuth flow."""
        # Don't call authenticate() here - it's handled by the base class
        # Just build and return the service
        return build('calendar', 'v3', credentials=self.creds)

    async def get_upcoming_events(self, query: str = None, max_results: int = 10) -> List[Dict[str, Any]]:
        """Asynchronously get upcoming events from the user's calendar."""
        try:
            def fetch():
                now = datetime.utcnow().isoformat() + 'Z'
                time_min = now
                time_max = None

                if query:
                    # Parse natural language query into a date range
                    parsed_date = dateparser.parse(query, settings={'PREFER_DATES_FROM': 'future'})
                    if parsed_date:
                        time_min = parsed_date.isoformat() + 'Z'
                        # If query is like 'this week', set time_max to end of week
                        if 'week' in query.lower():
                            time_max = (parsed_date + timedelta(days=7)).isoformat() + 'Z'

                events_result = self.service.events().list(
                    calendarId='primary',
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                return events_result.get('items', [])
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error getting upcoming events: {e}")
            raise

    async def get_events_for_date(self, date: str) -> List[Dict[str, Any]]:
        """Asynchronously get events for a specific date."""
        try:
            def fetch():
                start_time = f"{date}T00:00:00Z"
                end_time = f"{date}T23:59:59Z"
                events_result = self.service.events().list(
                    calendarId='primary',
                    timeMin=start_time,
                    timeMax=end_time,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                return events_result.get('items', [])
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error getting events for date: {e}")
            raise

    def parse_date(self, dt_str):
        """Parse a date string, ensuring the year is included."""
        if not dt_str:
            return None
        
        # Get current year
        current_year = datetime.now().year
        
        # If the date string doesn't include a year, append it
        if not any(str(year) in dt_str for year in range(2000, 2100)):
            dt_str = f"{dt_str} {current_year}"
        
        return dateparser.parse(dt_str, settings={'PREFER_DATES_FROM': 'future'})

    def _parse_datetime(self, dt_str):
        """Parse a datetime string into a timezone-aware datetime object.
        If the string is a natural language date (e.g., 'tomorrow 10am'), use dateparser.
        Otherwise, use dateutil.parser.
        """
        try:
            # Try dateparser first for natural language
            dt = self.parse_date(dt_str)
            if dt is None:
                # Fallback to dateutil for ISO or common formats
                dt = dateutil_parser.parse(dt_str)
            # Ensure the datetime is timezone-aware
            if dt.tzinfo is None:
                dt = self.user_tz.localize(dt)
            return dt
        except Exception as e:
            print(f"Error parsing datetime: {e}")
            raise ValueError(f"Invalid datetime string: {dt_str}")

    async def check_for_conflicts(self, event_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Check for conflicting events at the specified time.
        Args:
            event_details (Dict[str, Any]): Event details including start and end times
        Returns:
            List[Dict[str, Any]]: List of conflicting events (empty if no conflicts)
        """
        try:
            start_time = event_details['start']['dateTime'] if isinstance(event_details['start'], dict) else event_details['start']
            end_time = event_details['end']['dateTime'] if isinstance(event_details['end'], dict) else event_details['end']
            
            # Parse the times to ensure they're in the correct format
            if isinstance(start_time, str):
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            else:
                start_dt = start_time
                
            if isinstance(end_time, str):
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            else:
                end_dt = end_time
            
            # Convert to UTC for API call
            if start_dt.tzinfo is None:
                start_dt = self.user_tz.localize(start_dt)
            if end_dt.tzinfo is None:
                end_dt = self.user_tz.localize(end_dt)
            
            start_utc = start_dt.astimezone(dt_timezone.utc).isoformat()
            end_utc = end_dt.astimezone(dt_timezone.utc).isoformat()
            
            def fetch():
                events_result = self.service.events().list(
                    calendarId='primary',
                    timeMin=start_utc,
                    timeMax=end_utc,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                return events_result.get('items', [])
            
            conflicting_events = await asyncio.to_thread(fetch)
            logger.info(f"Found {len(conflicting_events)} conflicting events")
            return conflicting_events
            
        except Exception as e:
            logger.error(f"Error checking for conflicts: {e}")
            raise

    async def write_event(self, event_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Asynchronously create a new calendar event.
        Args:
            event_details (Dict[str, Any]): Event details including summary, start, end, etc.
        Returns:
            Dict[str, Any]: Created event details
        """
        try:
            logger.info(f"Creating calendar event with details: {event_details}")
            required_fields = ['summary', 'start', 'end']
            missing_fields = [field for field in required_fields if field not in event_details]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            for time_field in ['start', 'end']:
                if isinstance(event_details[time_field], dict):
                    if 'dateTime' not in event_details[time_field]:
                        raise ValueError(f"Missing dateTime in {time_field}")
                else:
                    raise ValueError(f"Invalid {time_field} format")
            
            # Check for conflicts before creating the event
            conflicting_events = await self.check_for_conflicts(event_details)
            
            if conflicting_events:
                # Return conflict information instead of creating the event
                conflict_info = {
                    "type": "conflict",
                    "conflicting_events": conflicting_events,
                    "proposed_event": event_details,
                    "message": f"Found {len(conflicting_events)} conflicting event(s) at this time. Please review and decide how to proceed."
                }
                logger.info(f"Conflict detected: {conflict_info['message']}")
                return conflict_info
            
            # No conflicts, proceed with creating the event
            event = await asyncio.to_thread(
                lambda: self.service.events().insert(
                    calendarId='primary',
                    body=event_details
                ).execute()
            )
            logger.info(f"Successfully created event: {event.get('id')}")
            return event
        except ValueError as ve:
            logger.error(f"Validation error creating event: {ve}")
            raise
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}")
            raise

    async def write_event_with_conflict_resolution(self, event_details: Dict[str, Any], conflict_action: str = "skip") -> Dict[str, Any]:
        """
        Create a new calendar event with conflict resolution.
        Args:
            event_details (Dict[str, Any]): Event details including summary, start, end, etc.
            conflict_action (str): How to handle conflicts - "skip", "replace", or "delete"
        Returns:
            Dict[str, Any]: Created event details or conflict information
        """
        try:
            # Check for conflicts first
            conflicting_events = await self.check_for_conflicts(event_details)
            
            if conflicting_events:
                if conflict_action == "skip":
                    return {
                        "type": "conflict",
                        "conflicting_events": conflicting_events,
                        "proposed_event": event_details,
                        "message": f"Found {len(conflicting_events)} conflicting event(s). Skipping event creation."
                    }
                elif conflict_action == "replace":
                    # Delete all conflicting events
                    for event in conflicting_events:
                        await self.delete_event(event['id'])
                    logger.info(f"Deleted {len(conflicting_events)} conflicting events")
                elif conflict_action == "delete":
                    # Delete the first conflicting event only
                    if conflicting_events:
                        await self.delete_event(conflicting_events[0]['id'])
                        logger.info(f"Deleted conflicting event: {conflicting_events[0]['summary']}")
            
            # Now create the new event
            event = await asyncio.to_thread(
                lambda: self.service.events().insert(
                    calendarId='primary',
                    body=event_details
                ).execute()
            )
            logger.info(f"Successfully created event: {event.get('id')}")
            return event
            
        except Exception as e:
            logger.error(f"Error creating event with conflict resolution: {str(e)}")
            raise

    async def delete_event(self, event_id: str) -> None:
        """
        Asynchronously delete a calendar event by its ID.
        Args:
            event_id (str): The ID of the event to delete.
        """
        try:
            logger.info(f"Deleting calendar event with ID: {event_id}")
            await asyncio.to_thread(
                lambda: self.service.events().delete(
                    calendarId='primary',
                    eventId=event_id
                ).execute()
            )
            logger.info(f"Successfully deleted event: {event_id}")
        except Exception as e:
            logger.error(f"Error deleting event {event_id}: {e}")
            raise
