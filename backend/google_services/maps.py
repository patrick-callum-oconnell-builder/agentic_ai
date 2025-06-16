from typing import List, Dict, Any, Optional
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
import googlemaps

logger = logging.getLogger(__name__)

class GoogleMapsService(GoogleAPIService):
    """Service for interacting with Google Maps API."""
    
    def __init__(self):
        """Initialize the Google Maps service."""
        super().__init__('GOOGLE_MAPS_API_KEY')
        self.service = self.initialize_service()

    def get_directions(self, origin: str, destination: str, mode: str = "driving") -> Dict:
        """
        Get directions between two locations.
        
        Args:
            origin (str): Starting location
            destination (str): Ending location
            mode (str): Travel mode (driving, walking, bicycling, transit)
            
        Returns:
            Dict: Directions data
        """
        try:
            client = googlemaps.Client(key=self.api_key)
            return client.directions(origin, destination, mode=mode)
        except Exception as e:
            logger.error(f"Error getting directions: {e}")
            raise
            
    def get_place_details(self, place_id: str) -> Dict:
        """
        Get details for a specific place.
        
        Args:
            place_id (str): Google Place ID
            
        Returns:
            Dict: Place details
        """
        try:
            client = googlemaps.Client(key=self.api_key)
            return client.place(place_id)
        except Exception as e:
            logger.error(f"Error getting place details: {e}")
            raise
            
    def search_places(self, query: str, location: Optional[Dict[str, float]] = None, radius: Optional[int] = None) -> List[Dict]:
        """
        Search for places matching a query.
        
        Args:
            query (str): Search query
            location (Dict[str, float], optional): Location to search around (lat, lng)
            radius (int, optional): Search radius in meters
            
        Returns:
            List[Dict]: List of matching places
        """
        try:
            client = googlemaps.Client(key=self.api_key)
            return client.places(query, location=location, radius=radius)
        except Exception as e:
            logger.error(f"Error searching places: {e}")
            raise
            
    def get_distance_matrix(self, origins: List[str], destinations: List[str], mode: str = "driving") -> Dict:
        """
        Get distance and duration between multiple origins and destinations.
        
        Args:
            origins (List[str]): List of origin locations
            destinations (List[str]): List of destination locations
            mode (str): Travel mode (driving, walking, bicycling, transit)
            
        Returns:
            Dict: Distance matrix data
        """
        try:
            client = googlemaps.Client(key=self.api_key)
            return client.distance_matrix(origins, destinations, mode=mode)
        except Exception as e:
            logger.error(f"Error getting distance matrix: {e}")
            raise
            
    def __del__(self):
        """Cleanup when the service is destroyed."""
        self._client = None

    def find_nearby_workout_locations(self, location: Dict[str, float], radius: int = 5000) -> List[Dict]:
        """
        Find nearby workout locations using Google Maps.
        
        Args:
            location (Dict[str, float]): Location to search from (lat, lng)
            radius (int): Search radius in meters
            
        Returns:
            List[Dict]: List of location metadata
        """
        try:
            # Format location as a tuple
            location_tuple = (location['lat'], location['lng'])
            # Use the googlemaps client to search for gyms and fitness centers
            places_result = self.service.places_nearby(
                location=location_tuple,
                radius=radius,
                type='gym'
            )
            return places_result.get('results', [])
        except Exception as e:
            logger.error(f"Error finding nearby workout locations: {e}")
            raise

    def get_location_details(self, place_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific location."""
        try:
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
        except Exception as e:
            print(f"Error getting location details: {e}")
            return {}

    def find_running_trails(self, location: Dict[str, float], radius: int = 5000) -> List[Dict[str, Any]]:
        try:
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
                    'name': result['name'],
                    'address': result.get('vicinity', ''),
                    'rating': result.get('rating', 0),
                    'location': result['geometry']['location']
                })
            return trails
        except Exception as e:
            print(f"Error finding running trails: {e}")
            return []
        finally:
            gc.collect() 

    def authenticate(self):
        # No-op for API key
        pass 

    def initialize_service(self):
        """Initialize the Google Maps service."""
        return googlemaps.Client(key=self.api_key) 