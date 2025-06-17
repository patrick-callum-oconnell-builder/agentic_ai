from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from typing import List, Dict, Any
import logging
from datetime import datetime, timedelta
from backend.google_services.base import GoogleServiceBase
import asyncio

logger = logging.getLogger(__name__)

class GoogleFitnessService(GoogleServiceBase):
    """Service for interacting with Google Fitness API."""
    
    SCOPES = ['https://www.googleapis.com/auth/fitness.activity.read']
    
    def __init__(self):
        """Initialize the Fitness service."""
        super().__init__()
        # Note: authenticate() is now async, but __init__ cannot be async
        # We'll handle authentication in initialize_service instead

    async def initialize_service(self):
        """Initialize the Google Fitness service."""
        # Don't call authenticate() here - it's handled by the base class
        return build('fitness', 'v1', credentials=self.creds)

    async def get_activities(self, days: int = 7) -> List[Dict[str, Any]]:
        """Asynchronously get recent fitness activities."""
        try:
            def fetch():
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=days)
                activities = self.service.users().dataset().aggregate(
                    userId='me',
                    body={
                        'aggregateBy': [{
                            'dataTypeName': 'com.google.activity.segment'
                        }],
                        'bucketByTime': {'durationMillis': 86400000},
                        'startTimeMillis': int(start_time.timestamp() * 1000),
                        'endTimeMillis': int(end_time.timestamp() * 1000)
                    }
                ).execute()
                return activities.get('bucket', [])
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error fetching fitness activities: {e}")
            raise

    async def get_activity_summary(self) -> Dict:
        """Asynchronously get a summary of user's fitness activities."""
        try:
            def fetch():
                # Note: This will be called in a thread, so we need to handle the async call differently
                pass
            
            # Get activities asynchronously
            activities = await self.get_activities()
            
            summary = {
                'total_activities': len(activities),
                'activity_types': {},
                'total_duration': 0
            }
            
            for bucket in activities:
                for dataset in bucket.get('dataset', []):
                    for point in dataset.get('point', []):
                        activity_type = point.get('value', [{}])[0].get('stringValue', 'unknown')
                        duration = int(point.get('value', [{}])[0].get('intVal', 0))
                        
                        summary['activity_types'][activity_type] = summary['activity_types'].get(activity_type, 0) + 1
                        summary['total_duration'] += duration
            
            return summary
        except Exception as e:
            logger.error(f"Error getting activity summary: {e}")
            raise
            
    async def get_activity_details(self, activity_id: str) -> Dict:
        """Asynchronously get details for a specific activity."""
        try:
            def fetch():
                activity = self.service.users().sessions().get(
                    userId='me',
                    sessionId=activity_id
                ).execute()
                
                return activity
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error getting activity details: {e}")
            raise

    async def get_workout_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Asynchronously get workout history for the last n days."""
        try:
            def fetch():
                end_time = datetime.now()
                start_time = end_time - timedelta(days=days)
                workouts = self.service.users().sessions().list(
                    userId='me',
                    startTime=f"{int(start_time.timestamp() * 1000000)}",
                    endTime=f"{int(end_time.timestamp() * 1000000)}"
                ).execute()
                return workouts.get('session', [])
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error getting workout history: {e}")
            raise

    async def get_body_metrics(self) -> Dict[str, Any]:
        """Asynchronously get current body metrics (weight, height, etc.)."""
        try:
            def fetch():
                end_time = datetime.now()
                start_time = end_time - timedelta(days=7)
                weight = self.service.users().dataSources().datasets().get(
                    userId='me',
                    dataSourceId='derived:com.google.weight:com.google.android.gms:merge_weight',
                    datasetId=f"{int(start_time.timestamp() * 1000000)}-{int(end_time.timestamp() * 1000000)}"
                ).execute()
                height = self.service.users().dataSources().datasets().get(
                    userId='me',
                    dataSourceId='derived:com.google.height:com.google.android.gms:merge_height',
                    datasetId=f"{int(start_time.timestamp() * 1000000)}-{int(end_time.timestamp() * 1000000)}"
                ).execute()
                return {
                    'weight': weight,
                    'height': height
                }
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error getting body metrics: {e}")
            raise 