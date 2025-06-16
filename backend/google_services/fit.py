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

logger = logging.getLogger(__name__)

class GoogleFitnessService(GoogleServiceBase):
    """Service for interacting with Google Fitness API."""
    
    SCOPES = ['https://www.googleapis.com/auth/fitness.activity.read']
    
    def __init__(self):
        """Initialize the Fitness service."""
        super().__init__()
        self.authenticate()

    def initialize_service(self):
        """Initialize the Google Fitness service."""
        return build('fitness', 'v1', credentials=self.creds)

    def get_activities(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent fitness activities."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)
            
            activities = self.service.users().dataset().aggregate(
                userId='me',
                body={
                    'aggregateBy': [{
                        'dataTypeName': 'com.google.activity.segment'
                    }],
                    'bucketByTime': {'durationMillis': 86400000},  # 24 hours
                    'startTimeMillis': int(start_time.timestamp() * 1000),
                    'endTimeMillis': int(end_time.timestamp() * 1000)
                }
            ).execute()
            
            return activities.get('bucket', [])
        except Exception as e:
            logger.error(f"Error fetching fitness activities: {e}")
            raise

    def get_activity_summary(self) -> Dict:
        """
        Get a summary of user's fitness activities.
        
        Returns:
            Dict: Activity summary data
        """
        try:
            activities = self.get_activities()
            
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
            
    def get_activity_details(self, activity_id: str) -> Dict:
        """
        Get details for a specific activity.
        
        Args:
            activity_id (str): ID of the activity to retrieve
            
        Returns:
            Dict: Activity details
        """
        try:
            activity = self.service.users().sessions().get(
                userId='me',
                sessionId=activity_id
            ).execute()
            
            return activity
        except Exception as e:
            logger.error(f"Error getting activity details: {e}")
            raise

    def get_workout_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get workout history for the last n days."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            workouts = self.service.users().sessions().list(
                userId='me',
                startTime=f"{int(start_time.timestamp() * 1000000)}",
                endTime=f"{int(end_time.timestamp() * 1000000)}"
            ).execute()
            return workouts.get('session', [])
        except Exception as e:
            logger.error(f"Error getting workout history: {e}")
            raise

    def get_body_metrics(self) -> Dict[str, Any]:
        """Get current body metrics (weight, height, etc.)."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=7)  # Last 7 days of body metrics
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
        except Exception as e:
            logger.error(f"Error getting body metrics: {e}")
            raise 