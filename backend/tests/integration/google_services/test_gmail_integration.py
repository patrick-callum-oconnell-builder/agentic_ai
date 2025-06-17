import os
import sys
import pytest

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

@pytest.mark.asyncio
async def test_get_recent_emails(agent):
    # Explicitly await the agent fixture
    agent_instance = await agent
    try:
        # Fetch recent emails using the agent's gmail service
        emails = await agent_instance.gmail_service.get_recent_emails()
        assert isinstance(emails, list)
        print(f"Gmail test: Successfully fetched {len(emails)} emails")
    except Exception as e:
        pytest.fail(f"Failed to fetch emails: {str(e)}")

if __name__ == '__main__':
    pytest.main() 