from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import requests
import gc
import os
import logging
import pickle
from backend.google_services.base import GoogleAPIService
from googlemaps import Client
import asyncio

logger = logging.getLogger(__name__)

class GoogleMapsService(GoogleAPIService):
    """Service for interacting with Google Maps API."""
    
    def __init__(self, api_key: str):
        """Initialize the Google Maps service with an API key."""
        super().__init__(api_key)
        self.client = Client(key=self.api_key)
        self.places_service = self.client.places
        self.directions_service = self.client.directions

    async def get_directions(self, origin: str, destination: str) -> str:
        """Get directions between two locations using the Routes API."""
        try:
            # Use the new Routes API
            result = self.directions_service(
                origin=origin,
                destination=destination,
                mode="driving",
                alternatives=True
            )
            
            if not result:
                return "No directions found."
            
            # Format the directions
            directions = []
            for route in result:
                steps = []
                for step in route['legs'][0]['steps']:
                    steps.append(step['html_instructions'])
                directions.append({
                    'distance': route['legs'][0]['distance']['text'],
                    'duration': route['legs'][0]['duration']['text'],
                    'steps': steps
                })
            
            # Format the response
            response = []
            for i, route in enumerate(directions, 1):
                response.append(f"Route {i}:")
                response.append(f"Distance: {route['distance']}")
                response.append(f"Duration: {route['duration']}")
                response.append("Steps:")
                for step in route['steps']:
                    response.append(f"- {step}")
                response.append("")
            
            return "\n".join(response)
            
        except Exception as e:
            logger.error(f"Error getting directions: {str(e)}")
            return f"Error getting directions: {str(e)}"

    async def find_nearby_places(self, location: str, radius: int = 5000, type: str = "gym") -> str:
        """Find nearby places using the Places API."""
        try:
            # Use the new Places API
            result = self.places_service.nearby_search(
                location=location,
                radius=radius,
                type=type
            )
            
            if not result or 'results' not in result:
                return "No places found."
            
            # Format the results
            places = []
            for place in result['results']:
                places.append({
                    'name': place['name'],
                    'address': place.get('vicinity', 'No address available'),
                    'rating': place.get('rating', 'No rating'),
                    'types': place.get('types', [])
                })
            
            # Format the response
            response = []
            for i, place in enumerate(places, 1):
                response.append(f"{i}. {place['name']}")
                response.append(f"   Address: {place['address']}")
                response.append(f"   Rating: {place['rating']}")
                response.append(f"   Types: {', '.join(place['types'])}")
                response.append("")
            
            return "\n".join(response)
            
        except Exception as e:
            logger.error(f"Error finding nearby places: {str(e)}")
            return f"Error finding nearby places: {str(e)}"

    async def get_place_details(self, place_id: str) -> Dict:
        """Asynchronously get detailed information about a place."""
        try:
            def fetch():
                return self.client.place(place_id)
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error getting place details: {e}")
            raise

    async def search_places(self, query: str, location: Optional[Dict[str, float]] = None, radius: int = 5000) -> Dict:
        """Asynchronously search for places matching a query."""
        try:
            def search():
                return self.client.places(query, location=location, radius=radius)
            return await asyncio.to_thread(search)
        except Exception as e:
            logger.error(f"Error searching places: {e}")
            raise

    async def get_distance_matrix(self, origins: List[str], destinations: List[str], mode: str = "driving") -> Dict:
        """Asynchronously get distance and duration between multiple origins and destinations."""
        try:
            def fetch():
                return self.client.distance_matrix(origins, destinations, mode=mode)
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error getting distance matrix: {e}")
            raise

    def __del__(self):
        """Cleanup when the service is destroyed."""
        self.client = None

    async def find_nearby_workout_locations(self, location_or_address):
        """Find nearby gyms or fitness centers given an address or lat/lng."""
        try:
            if isinstance(location_or_address, str):
                # Geocode the address to get lat/lng
                lat, lng = await self.geocode_address(location_or_address)
            elif isinstance(location_or_address, dict):
                lat = location_or_address.get('lat')
                lng = location_or_address.get('lng')
                if lat is None or lng is None:
                    raise ValueError("Missing lat/lng in location dict.")
            else:
                raise ValueError("Invalid location input.")
            # Now search for gyms/fitness centers
            return await self._find_places_nearby(lat, lng, type_filter=['gym', 'fitness'])
        except Exception as e:
            logger.error(f"Error finding nearby workout locations: {e}")
            return []

    async def get_location_details(self, place_id: str) -> Dict[str, Any]:
        """Asynchronously get detailed information about a specific location."""
        try:
            def fetch():
                url = 'https://maps.googleapis.com/maps/api/place/details/json'
                params = {
                    'place_id': place_id,
                    'key': self.api_key
                }
                response = requests.get(url, params=params)
                data = response.json()
                if data['status'] == 'OK':
                    return data['result']
                else:
                    print(f"Error getting location details: {data['status']}")
                    return {}
            return await asyncio.to_thread(fetch)
        except Exception as e:
            print(f"Error getting location details: {e}")
            return {}

    async def find_running_trails(self, location: Dict[str, float], radius: int = 5000) -> List[Dict[str, Any]]:
        """Asynchronously find running trails near a location."""
        try:
            def search():
                params = {
                    "location": f"{location['lat']},{location['lng']}",
                    "radius": radius,
                    "keyword": "running trail",
                    "key": self.api_key
                }
                url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                response = requests.get(url, params=params)
                response.raise_for_status()
                results = response.json()
                trails = []
                for result in results.get('results', []):
                    trails.append({
                        'name': result.get('name', 'Unknown'),
                        'address': result.get('vicinity', 'No address'),
                        'rating': result.get('rating', 'No rating'),
                        'place_id': result.get('place_id', ''),
                        'location': result.get('geometry', {}).get('location', {})
                    })
                return trails
            return await asyncio.to_thread(search)
        except Exception as e:
            logger.error(f"Error finding running trails: {e}")
            return []
        finally:
            gc.collect() 

    def authenticate(self):
        # No-op for API key
        pass 

    def initialize_service(self):
        """Initialize the Google Maps service."""
        return self.client 

    async def geocode_address(self, address: str):
        """Geocode an address to (lat, lng) using the Google Maps API."""
        try:
            def geocode():
                result = self.client.geocode(address)
                if not result:
                    raise ValueError(f"No geocoding result for address: {address}")
                location = result[0]['geometry']['location']
                return location['lat'], location['lng']
            return await asyncio.to_thread(geocode)
        except Exception as e:
            logger.error(f"Error geocoding address '{address}': {e}")
            raise 

    async def _find_places_nearby(self, lat, lng, type_filter=None, radius=50000):
        """Find places nearby given lat/lng and type filter."""
        try:
            def search():
                params = {
                    "location": f"{lat},{lng}",
                    "radius": radius,
                    "key": self.api_key,
                    "type": "gym"
                }
                url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                results = response.json().get('results', [])
                places = []
                for result in results:
                    places.append({
                        'name': result.get('name', 'Unknown'),
                        'address': result.get('vicinity', 'No address'),
                        'rating': result.get('rating', 'No rating'),
                        'place_id': result.get('place_id', ''),
                        'location': result.get('geometry', {}).get('location', {})
                    })
                return places
            return await asyncio.to_thread(search)
        except Exception as e:
            logger.error(f"Error finding places nearby: {e}")
            return [] 