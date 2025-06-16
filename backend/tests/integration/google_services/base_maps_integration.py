import os
import sys
import pytest
from dotenv import load_dotenv
from backend.google_services.maps import GoogleMapsService
from backend.agent import PersonalTrainerAgent

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(backend_dir)

@pytest.fixture(scope="class")
def maps_service(request):
    load_dotenv()
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        pytest.skip("Missing required environment variable: GOOGLE_MAPS_API_KEY")
    service = GoogleMapsService()
    service.authenticate()
    return service

@pytest.fixture(scope="class")
async def agent(maps_service, request):
    agent = await PersonalTrainerAgent.ainit(maps_service=maps_service)
    return agent

class BaseGoogleMapsIntegrationTest:
    pass 