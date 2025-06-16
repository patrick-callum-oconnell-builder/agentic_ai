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
from googlemaps import Client
import asyncio
from googlemaps.exceptions import ApiError

logger = logging.getLogger(__name__)

class GoogleMapsService(GoogleAPIService):
    """Service for interacting with Google Maps API."""
    
    def __init__(self):
        """Initialize the Google Maps service."""
        self.timeout = 10  # seconds
        super().__init__('GOOGLE_MAPS_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY environment variable not set")
        self.service = self.initialize_service()
        logger.info("GoogleMapsService initialized with API key")

    def initialize_service(self):
        """Initialize the Google Maps service."""
        if not self.api_key:
            raise ValueError("Google Maps API key not set")
        logger.info("Initializing Google Maps client")
        try:
            client = Client(key=self.api_key, timeout=self.timeout)
            # Test the client with a simple geocode request
            client.geocode("New York, NY")
            logger.info("Successfully validated Google Maps API key")
            return client
        except Exception as e:
            logger.error(f"Failed to initialize Google Maps client: {e}")
            raise ValueError(f"Invalid Google Maps API key: {e}")

    async def geocode_address(self, address: str) -> Dict[str, float]:
        """
        Convert an address to coordinates asynchronously.
        
        Args:
            address (str): Address to geocode
            
        Returns:
            Dict[str, float]: Dictionary with 'lat' and 'lng' keys
        """
        try:
            logger.info(f"Geocoding address: {address}")
            # Run the synchronous geocode call in a thread pool
            result = await asyncio.to_thread(
                self.service.geocode,
                address
            )
            if result and len(result) > 0:
                location = result[0]['geometry']['location']
                logger.info(f"Successfully geocoded address to: {location}")
                return {
                    'lat': location['lat'],
                    'lng': location['lng']
                }
            else:
                logger.error(f"Could not geocode address: {address}")
                raise ValueError(f"Could not geocode address: {address}")
        except Exception as e:
            logger.error(f"Error geocoding address: {e}")
            raise

    async def search_places(self, query: str, location: Optional[Dict[str, float]] = None, radius: Optional[int] = None, max_results: int = 10) -> List[Dict]:
        """
        Search for places matching a query asynchronously.
        
        Args:
            query (str): Search query
            location (Dict[str, float], optional): Location to search around (lat, lng)
            radius (int, optional): Search radius in meters
            max_results (int, optional): Maximum number of results to return (default 10)
            
        Returns:
            List[Dict]: List of matching places
        """
        try:
            logger.info(f"Searching places with query: {query}, location: {location}, radius: {radius}")
            # Run the synchronous places search in a thread pool
            places = await asyncio.to_thread(
                self.service.places,
                query,
                location=location,
                radius=radius
            )
            
            results = places.get('results', [])
            logger.info(f"Found {len(results)} places, limiting to {max_results}")
            
            # Limit results and format them
            limited_results = []
            for place in results[:max_results]:
                formatted_place = {
                    'name': place.get('name', 'Unknown'),
                    'address': place.get('formatted_address', 'No address available'),
                    'rating': place.get('rating', 'No rating'),
                    'place_id': place.get('place_id'),
                    'types': place.get('types', [])
                }
                limited_results.append(formatted_place)
            
            return limited_results
            
        except Exception as e:
            logger.error(f"Error searching places: {e}")
            raise ValueError(f"Failed to search places: {str(e)}")

    async def get_place_details(self, place_id: str) -> Dict:
        """
        Get detailed information about a place asynchronously.
        
        Args:
            place_id (str): Google Places ID
            
        Returns:
            Dict: Place details
        """
        try:
            logger.info(f"Getting details for place: {place_id}")
            # Run the synchronous place details request in a thread pool
            details = await asyncio.to_thread(
                self.service.place,
                place_id
            )
            return details.get('result', {})
        except Exception as e:
            logger.error(f"Error getting place details: {e}")
            raise

    async def get_directions(self, origin: str, destination: str, mode: str = "driving") -> List[Dict]:
        """
        Get directions between two locations asynchronously.
        
        Args:
            origin (str): Starting location
            destination (str): Ending location
            mode (str): Travel mode (driving, walking, bicycling, transit)
            
        Returns:
            List[Dict]: List of route steps
        """
        try:
            logger.info(f"Getting directions from {origin} to {destination} by {mode}")
            # Run the synchronous directions request in a thread pool
            directions = await asyncio.to_thread(
                self.service.directions,
                origin,
                destination,
                mode=mode
            )
            return directions
        except Exception as e:
            logger.error(f"Error getting directions: {e}")
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
            return self.service.distance_matrix(origins, destinations, mode=mode, timeout=self.timeout)
        except Exception as e:
            logger.error(f"Error getting distance matrix: {e}")
            raise

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
                type='gym',
                timeout=self.timeout
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
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            if data['status'] == 'OK':
                return data['result']
            else:
                logger.error(f"Error getting location details: {data['status']}")
                return {}
        except Exception as e:
            logger.error(f"Error getting location details: {e}")
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
            response = requests.get(url, params=params, timeout=self.timeout)
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
            logger.error(f"Error finding running trails: {e}")
            return []
        finally:
            gc.collect() 