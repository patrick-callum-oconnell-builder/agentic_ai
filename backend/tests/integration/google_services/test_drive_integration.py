import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.integration.google_services.base_google_integration import BaseGoogleIntegrationTest
from agent import PersonalTrainerAgent
from google_services.drive import GoogleDriveService

class TestDriveIntegration(BaseGoogleIntegrationTest):
    """Test suite for Google Drive integration."""
    
    def test_create_folder(self):
        """Test creating a workout folder."""
        try:
            # Create a workout folder using the agent's drive service
            folder = self.agent.drive_service.create_folder("Workout Plans")
            self.assertIsNotNone(folder)
            self.assertIn('id', folder)
            print(f"Drive test: Successfully created workout folder")
        except Exception as e:
            self.fail(f"Failed to create workout folder: {str(e)}")
            
    def test_upload_workout_plan(self):
        """Test uploading a workout plan."""
        try:
            # Create a test workout plan file
            import tempfile
            import json
            
            workout_plan = {
                "name": "Upper Body Workout Plan",
                "description": "Focus on chest and shoulders",
                "exercises": [
                    {"name": "Bench Press", "sets": 3, "reps": 10},
                    {"name": "Shoulder Press", "sets": 3, "reps": 12}
                ]
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(workout_plan, f)
                temp_file_path = f.name
            
            # Upload the workout plan using the agent's drive service
            result = self.agent.drive_service.upload_file(temp_file_path, name="Upper Body Workout Plan.json")
            self.assertIsNotNone(result)
            self.assertIn('id', result)
            print(f"Drive test: Successfully uploaded workout plan")
            
            # Clean up the temporary file
            os.unlink(temp_file_path)
        except Exception as e:
            self.fail(f"Failed to upload workout plan: {str(e)}")

if __name__ == '__main__':
    unittest.main() 