import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.integration.google_services.base_google_integration import BaseGoogleIntegrationTest
from agent import PersonalTrainerAgent
from google_services.tasks import GoogleTasksService

class TestTasksIntegration(BaseGoogleIntegrationTest):
    """Test suite for Google Tasks integration."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a workout task list and store its ID for use in other tests
        cls.tasklist = cls.agent.tasks_service.create_workout_tasklist()
        cls.tasklist_id = cls.tasklist.get('id')

    def test_create_workout_tasklist(self):
        """Test creating a workout task list."""
        self.assertIsNotNone(self.tasklist)
        self.assertIn('id', self.tasklist)
        print(f"Tasks test: Successfully created workout task list with id {self.tasklist_id}")

    def test_add_workout_task(self):
        """Test adding a workout task."""
        try:
            # Create a test workout task
            workout_name = "Upper Body Workout"
            notes = "Focus on chest and shoulders"
            due_date = datetime(2024, 3, 21, 10, 0, 0).isoformat() + 'Z'
            # Add the task using the agent's tasks service
            result = self.agent.tasks_service.add_workout_task(
                tasklist_id=self.tasklist_id,
                workout_name=workout_name,
                notes=notes,
                due_date=due_date
            )
            self.assertIsNotNone(result)
            self.assertIn('id', result)
            print(f"Tasks test: Successfully added workout task")
        except Exception as e:
            self.fail(f"Failed to add workout task: {str(e)}")

if __name__ == '__main__':
    unittest.main() 