from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import List, Dict, Optional, Any, Union
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

    async def get_upcoming_events(self, args: Union[str, Dict[str, Any]] = None, max_results: int = 10) -> List[Dict[str, Any]]:
        """Asynchronously get upcoming events from the user's calendar."""
        try:
            def fetch():
                # Always use timezone-aware datetimes
                now = datetime.now(dt_timezone.utc)
                time_min = now.isoformat()
                time_max = None

                # Extract query from args if it's a dictionary
                query = args.get('query') if isinstance(args, dict) else args

                if query and isinstance(query, str):
                    # Parse natural language query into a date range
                    if 'week' in query.lower():
                        # Set time_min to start of current week (Monday)
                        start_of_week = now - timedelta(days=now.weekday())
                        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
                        time_min = start_of_week.isoformat()
                        # Set time_max to end of week (Sunday)
                        end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
                        time_max = end_of_week.isoformat()
                    else:
                        # Parse other natural language queries
                        parsed_date = dateparser.parse(query, settings={'PREFER_DATES_FROM': 'future'})
                        if parsed_date:
                            # Ensure parsed date is timezone-aware
                            if parsed_date.tzinfo is None:
                                parsed_date = parsed_date.replace(tzinfo=dt_timezone.utc)
                            time_min = parsed_date.isoformat()

                events_result = self.service.events().list(
                    calendarId='primary',
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()

                # Filter out events that don't match our criteria
                events = events_result.get('items', [])
                filtered_events = []
                for event in events:
                    # Skip birthday events more than a year away
                    if event.get('eventType') == 'birthday':
                        start = event.get('start', {})
                        if start.get('date'):  # All-day event
                            event_date = datetime.strptime(start['date'], '%Y-%m-%d').replace(tzinfo=dt_timezone.utc)
                            if (event_date - now).days > 365:
                                continue
                        elif start.get('dateTime'):  # Timed event
                            event_date = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                            if (event_date - now).days > 365:
                                continue
                    
                    # Skip events outside our time range
                    start = event.get('start', {})
                    if start.get('dateTime'):  # Timed event
                        event_start = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                        if time_max and event_start > datetime.fromisoformat(time_max.replace('Z', '+00:00')):
                            continue
                    elif start.get('date'):  # All-day event
                        event_date = datetime.strptime(start['date'], '%Y-%m-%d').replace(tzinfo=dt_timezone.utc)
                        if time_max and event_date > datetime.fromisoformat(time_max.replace('Z', '+00:00')):
                            continue
                    
                    filtered_events.append(event)
                return filtered_events[:max_results]

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
            
            # If no timezone info, assume Pacific Time
            if start_dt.tzinfo is None:
                start_dt = self.user_tz.localize(start_dt)
            if end_dt.tzinfo is None:
                end_dt = self.user_tz.localize(end_dt)
            
            # Convert to UTC for API call
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
                start and end can be:
                - dict with dateTime field and optional timeZone field
                - ISO format string
                - dict with date field for all-day events
        Returns:
            Dict[str, Any]: Created event details
        """
        try:
            logger.info(f"Creating calendar event with details: {event_details}")
            required_fields = ['summary', 'start', 'end']
            missing_fields = [field for field in required_fields if field not in event_details]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

            # Create a copy to avoid modifying the original
            event_details = event_details.copy()
            
            # Convert time formats if needed
            for time_field in ['start', 'end']:
                time_value = event_details[time_field]
                
                # If it's already in the correct format (dict with dateTime or date), leave it
                if isinstance(time_value, dict) and ('dateTime' in time_value or 'date' in time_value):
                    # If there's no timeZone field, add it
                    if 'dateTime' in time_value and 'timeZone' not in time_value:
                        time_value['timeZone'] = 'America/Los_Angeles'
                    continue
                
                # If it's a string, parse it
                if isinstance(time_value, str):
                    # Try to parse as datetime
                    try:
                        dt = dateparser.parse(time_value, settings={'PREFER_DATES_FROM': 'future'})
                        if dt:
                            # If no timezone info, assume Pacific Time
                            if dt.tzinfo is None:
                                dt = self.user_tz.localize(dt)
                            event_details[time_field] = {
                                'dateTime': dt.isoformat(),
                                'timeZone': 'America/Los_Angeles'
                            }
                            continue
                    except Exception as e:
                        logger.error(f"Error parsing {time_field} as datetime: {e}")
                
                # If we get here, the format is invalid
                raise ValueError(f"Invalid {time_field} format. Expected ISO datetime string or dict with dateTime/date field")
            
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

    async def list_events(self, start_time: str = None, end_time: str = None) -> List[Dict[str, Any]]:
        """List events within a time range.
        
        Args:
            start_time (str, optional): Start time in ISO format
            end_time (str, optional): End time in ISO format
            
        Returns:
            List[Dict[str, Any]]: List of events
        """
        try:
            def fetch():
                now = datetime.utcnow().isoformat() + 'Z'
                time_min = start_time or now
                time_max = end_time

                events_result = self.service.events().list(
                    calendarId='primary',
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                return events_result.get('items', [])
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error listing events: {e}")
            raise

    async def delete_events_in_range(self, time_range: Union[str, Dict[str, Any], None]) -> int:
        """
        Delete all events within a specified time range.
        Args:
            time_range (Union[str, Dict[str, Any], None]): Time range as string or dict with 'start' and 'end' keys
        Returns:
            int: Number of events deleted
        """
        try:
            def fetch():
                # Handle empty or None input
                if not time_range:
                    raise ValueError("Time range cannot be empty")

                # Handle both string and dictionary inputs
                if isinstance(time_range, dict):
                    # If it has a 'time_range' key, use that value
                    if 'time_range' in time_range:
                        time_range_str = time_range['time_range']
                        # Handle pipe-separated or comma-separated time ranges
                        if '|' in time_range_str:
                            start_str, end_str = time_range_str.split('|')
                        elif ',' in time_range_str:
                            start_str, end_str = time_range_str.split(',')
                        else:
                            start_str = time_range_str
                            end_str = None
                        
                        start_date = dateparser.parse(start_str, settings={'PREFER_DATES_FROM': 'future'})
                        end_date = dateparser.parse(end_str, settings={'PREFER_DATES_FROM': 'future'}) if end_str else None
                    # If it has start/end keys, use those
                    elif 'start' in time_range or 'end' in time_range:
                        start_str = time_range.get('start', '')
                        end_str = time_range.get('end', '')
                        if not start_str:
                            raise ValueError("Start time is required")
                        
                        start_date = dateparser.parse(start_str, settings={'PREFER_DATES_FROM': 'future'})
                        end_date = dateparser.parse(end_str, settings={'PREFER_DATES_FROM': 'future'}) if end_str else None
                    # Otherwise treat the dict as a string
                    else:
                        start_date = dateparser.parse(str(time_range), settings={'PREFER_DATES_FROM': 'future'})
                        end_date = None
                else:
                    # Handle string input
                    start_date = dateparser.parse(str(time_range).strip('"'), settings={'PREFER_DATES_FROM': 'future'})
                    end_date = None

                if not start_date:
                    raise ValueError(f"Could not parse time range: {time_range}")

                # Ensure dates are timezone-aware
                if start_date.tzinfo is None:
                    start_date = self.user_tz.localize(start_date)
                if end_date and end_date.tzinfo is None:
                    end_date = self.user_tz.localize(end_date)

                # Convert to UTC for API call
                start_utc = start_date.astimezone(dt_timezone.utc).isoformat()
                end_utc = end_date.astimezone(dt_timezone.utc).isoformat() if end_date else None

                # Get events in range
                events_result = self.service.events().list(
                    calendarId='primary',
                    timeMin=start_utc,
                    timeMax=end_utc,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()

                events = events_result.get('items', [])
                deleted_count = 0

                # Delete each event
                for event in events:
                    try:
                        self.service.events().delete(
                            calendarId='primary',
                            eventId=event['id']
                        ).execute()
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Error deleting event {event['id']}: {e}")
                        continue

                return deleted_count

            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error deleting events in range: {e}")
            raise
