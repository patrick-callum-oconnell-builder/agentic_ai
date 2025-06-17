import sys
import os
import pytest
from datetime import datetime, timezone

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

@pytest.mark.asyncio
async def test_create_workout_tasklist(agent):
    # Explicitly await the agent fixture
    agent_instance = await agent
    try:
        tasklist = await agent_instance.tasks_service.create_workout_tasklist()
        assert tasklist is not None
        assert 'id' in tasklist
        print(f"Tasks test: Successfully created workout task list with id {tasklist['id']}")
    except Exception as e:
        pytest.fail(f"Failed to create workout task list: {str(e)}")

@pytest.mark.asyncio
async def test_add_workout_task(agent):
    # Explicitly await the agent fixture
    agent_instance = await agent
    try:
        # First create a tasklist
        tasklist = await agent_instance.tasks_service.create_workout_tasklist()
        assert tasklist is not None
        assert 'id' in tasklist
        
        # Then add a task
        workout_name = "Upper Body Workout"
        notes = "Focus on chest and shoulders"
        due_date = datetime(2024, 3, 21, 10, 0, 0, tzinfo=timezone.utc)
        result = await agent_instance.tasks_service.add_workout_task(
            tasklist_id=tasklist['id'],
            workout_name=workout_name,
            notes=notes,
            due_date=due_date
        )
        assert result is not None
        assert 'id' in result
        print(f"Tasks test: Successfully added workout task")
    except Exception as e:
        pytest.fail(f"Failed to add workout task: {str(e)}")

if __name__ == '__main__':
    pytest.main() 