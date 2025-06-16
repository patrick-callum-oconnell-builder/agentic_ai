import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.integration.google_services.base_google_integration import BaseGoogleIntegrationTest
from agent import PersonalTrainerAgent
from google_services.calendar import GoogleCalendarService

class TestCalendarIntegration(BaseGoogleIntegrationTest):
    """Test suite for Google Calendar integration."""
    
    def test_fetch_upcoming_events(self):
        """Test fetching upcoming events."""
        try:
            # Fetch upcoming events using the agent's calendar service
            events = self.agent.calendar_service.get_upcoming_events()
            self.assertIsInstance(events, list)
            print(f"Calendar test: Successfully fetched {len(events)} upcoming events")
        except Exception as e:
            self.fail(f"Failed to fetch upcoming events: {str(e)}")
            
    def test_schedule_workout(self):
        """Test scheduling a workout."""
        try:
            # Create a test workout event
            workout = {
                "summary": "Upper Body Workout",
                "description": "Focus on chest and shoulders",
                "start": {
                    "dateTime": "2024-03-21T10:00:00Z",
                    "timeZone": "America/Los_Angeles"
                },
                "end": {
                    "dateTime": "2024-03-21T11:00:00Z",
                    "timeZone": "America/Los_Angeles"
                }
            }
            
            # Schedule the workout using the agent's calendar service
            result = self.agent.calendar_service.write_event(workout)
            self.assertIsNotNone(result)
            self.assertIn('id', result)
            print(f"Calendar test: Successfully scheduled workout")
        except Exception as e:
            self.fail(f"Failed to schedule workout: {str(e)}")

if __name__ == '__main__':
    unittest.main() 