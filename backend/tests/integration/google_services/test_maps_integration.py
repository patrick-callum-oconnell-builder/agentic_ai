import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv
from backend.agent import PersonalTrainerAgent
from backend.google_services.maps import GoogleMapsService
from tests.integration.google_services.base_maps_integration import BaseGoogleMapsIntegrationTest

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Load environment variables
load_dotenv()

@pytest.mark.asyncio
class TestMapsIntegration(BaseGoogleMapsIntegrationTest):
    async def test_find_nearby_workout_locations(self):
        messages = [{
            "role": "user",
            "content": "Find me workout locations near 1 Infinite Loop, Cupertino, CA"
        }]
        response = await self.agent.process_messages(messages)
        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0
        assert "workout" in response.lower()
        assert "location" in response.lower()

if __name__ == '__main__':
    pytest.main() 