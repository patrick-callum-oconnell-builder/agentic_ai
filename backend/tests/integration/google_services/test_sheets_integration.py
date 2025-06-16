import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.integration.google_services.base_google_integration import BaseGoogleIntegrationTest
from agent import PersonalTrainerAgent
from google_services.sheets import GoogleSheetsService

class TestSheetsIntegration(BaseGoogleIntegrationTest):
    """Test suite for Google Sheets integration."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a workout tracker and store its ID for use in other tests
        cls.spreadsheet = cls.agent.sheets_service.create_workout_tracker("Workout Tracker")
        cls.spreadsheet_id = cls.spreadsheet.get('spreadsheetId')

    def test_create_workout_tracker(self):
        """Test creating a workout tracker spreadsheet."""
        self.assertIsNotNone(self.spreadsheet)
        self.assertIn('spreadsheetId', self.spreadsheet)
        print(f"Sheets test: Successfully created workout tracker with id {self.spreadsheet_id}")

    def test_add_workout_entry(self):
        """Test adding a workout entry to the tracker."""
        try:
            # Create a test workout entry
            date = "2024-03-21"
            workout_type = "Upper Body"
            duration = "60"
            calories = "300"
            notes = "Focus on chest and shoulders"
            
            # Add the entry using the agent's sheets service
            result = self.agent.sheets_service.add_workout_entry(
                spreadsheet_id=self.spreadsheet_id,
                date=date,
                workout_type=workout_type,
                duration=duration,
                calories=calories,
                notes=notes
            )
            self.assertIsNotNone(result)
            self.assertIn('updates', result)
            print(f"Sheets test: Successfully added workout entry")
        except Exception as e:
            self.fail(f"Failed to add workout entry: {str(e)}")

if __name__ == '__main__':
    unittest.main() 