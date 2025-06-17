import os
import sys
import pytest

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

@pytest.mark.asyncio
async def test_create_workout_tracker(agent):
    # Explicitly await the agent fixture
    agent_instance = await agent
    try:
        spreadsheet = agent_instance.sheets_service.create_workout_tracker("Workout Tracker")
        assert spreadsheet is not None
        assert 'spreadsheetId' in spreadsheet
        print(f"Sheets test: Successfully created workout tracker with id {spreadsheet['spreadsheetId']}")
    except Exception as e:
        pytest.fail(f"Failed to create workout tracker: {str(e)}")

@pytest.mark.asyncio
async def test_add_workout_entry(agent):
    # Explicitly await the agent fixture
    agent_instance = await agent
    try:
        # First create a spreadsheet
        spreadsheet = agent_instance.sheets_service.create_workout_tracker("Workout Tracker")
        assert spreadsheet is not None
        assert 'spreadsheetId' in spreadsheet
        
        # Then add an entry
        date = "2024-03-21"
        workout_type = "Upper Body"
        duration = "60"
        calories = "300"
        notes = "Focus on chest and shoulders"
        result = agent_instance.sheets_service.add_workout_entry(
            spreadsheet_id=spreadsheet['spreadsheetId'],
            date=date,
            workout_type=workout_type,
            duration=duration,
            calories=calories,
            notes=notes
        )
        assert result is not None
        assert 'updates' in result
        print(f"Sheets test: Successfully added workout entry")
    except Exception as e:
        pytest.fail(f"Failed to add workout entry: {str(e)}")

if __name__ == '__main__':
    pytest.main() 