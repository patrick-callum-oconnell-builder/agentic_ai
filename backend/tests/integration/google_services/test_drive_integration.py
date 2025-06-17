import os
import sys
import pytest
import tempfile
import json

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

@pytest.mark.asyncio
async def test_create_folder(agent):
    """Test creating a workout folder."""
    # Explicitly await the agent fixture
    agent_instance = await agent
    try:
        folder = await agent_instance.drive_service.create_folder("Workout Plans")
        assert folder is not None
        assert 'id' in folder
        print(f"Drive test: Successfully created workout folder")
    except Exception as e:
        pytest.fail(f"Failed to create workout folder: {str(e)}")
        
@pytest.mark.asyncio
async def test_upload_workout_plan(agent):
    """Test uploading a workout plan."""
    # Explicitly await the agent fixture
    agent_instance = await agent
    try:
        # Create a test workout plan file
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
        
        # Upload the workout plan using the agent's drive service (not async)
        result = agent_instance.drive_service.upload_file(temp_file_path, name="Upper Body Workout Plan.json")
        assert result is not None
        assert 'id' in result
        print(f"Drive test: Successfully uploaded workout plan")
        
        # Clean up the temporary file
        os.unlink(temp_file_path)
    except Exception as e:
        pytest.fail(f"Failed to upload workout plan: {str(e)}")

if __name__ == '__main__':
    pytest.main() 