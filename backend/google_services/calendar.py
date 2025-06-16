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

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.pickle.
class GoogleCalendarService(GoogleServiceBase):
    """Service for interacting with Google Calendar API."""
    
    def __init__(self):
        """Initialize the Calendar service."""
        self.SCOPES = ['https://www.googleapis.com/auth/calendar']
        self.creds = None
        self.service = self.initialize_service()
        self.user_tz = timezone('America/Los_Angeles')

    def initialize_service(self):
        """Initialize the Google Calendar service using the new OAuth flow."""
        self.creds = get_google_credentials()
        return build('calendar', 'v3', credentials=self.creds)

    def get_upcoming_events(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Get upcoming events from the user's calendar.
        
        Args:
            max_results (int): Maximum number of events to return
            
        Returns:
            List[Dict[str, Any]]: List of upcoming events
        """
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            return events_result.get('items', [])
        except Exception as e:
            logger.error(f"Error getting upcoming events: {e}")
            raise

    def get_events_for_date(self, date: str) -> List[Dict[str, Any]]:
        """
        Get events for a specific date.
        
        Args:
            date (str): Date in YYYY-MM-DD format
            
        Returns:
            List[Dict[str, Any]]: List of events for the date
        """
        try:
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

    def write_event(self, event_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new calendar event.
        
        Args:
            event_details (Dict[str, Any]): Event details including summary, start, end, etc.
            
        Returns:
            Dict[str, Any]: Created event details
        """
        try:
            logger.info(f"Creating calendar event with details: {event_details}")
            
            # Validate required fields
            required_fields = ['summary', 'start', 'end']
            missing_fields = [field for field in required_fields if field not in event_details]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
            # Ensure start and end times are properly formatted
            for time_field in ['start', 'end']:
                if isinstance(event_details[time_field], dict):
                    if 'dateTime' not in event_details[time_field]:
                        raise ValueError(f"Missing dateTime in {time_field}")
                else:
                    raise ValueError(f"Invalid {time_field} format")
            
            event = self.service.events().insert(
                calendarId='primary',
                body=event_details
            ).execute()
            
            logger.info(f"Successfully created event: {event.get('id')}")
            return event
            
        except ValueError as ve:
            logger.error(f"Validation error creating event: {ve}")
            raise
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}")
            raise

    def authenticate(self):
        """Authenticate with Google Calendar API."""
        self.creds = get_google_credentials()
        self.service = build('calendar', 'v3', credentials=self.creds)

    def delete_event(self, event_id: str) -> None:
        """
        Delete a calendar event by its ID.
        Args:
            event_id (str): The ID of the event to delete.
        """
        try:
            logger.info(f"Deleting calendar event with ID: {event_id}")
            self.service.events().delete(
                calendarId='primary',
                eventId=event_id
            ).execute()
            logger.info(f"Successfully deleted event: {event_id}")
        except Exception as e:
            logger.error(f"Error deleting event {event_id}: {e}")
            raise
