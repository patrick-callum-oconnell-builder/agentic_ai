from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from typing import List, Dict, Optional, Any
import logging
from backend.google_services.base import GoogleServiceBase
from backend.google_services.auth import get_google_credentials

logger = logging.getLogger(__name__)

class GoogleSheetsService(GoogleServiceBase):
    """Service for interacting with Google Sheets API."""
    
    def __init__(self):
        """Initialize the Sheets service."""
        self.SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        self.creds = None
        self.service = self.initialize_service()

    def initialize_service(self):
        """Initialize the Google Sheets service using the new OAuth flow."""
        self.creds = get_google_credentials()
        return build('sheets', 'v4', credentials=self.creds)

    def create_spreadsheet(self, title: str) -> Dict:
        """
        Create a new spreadsheet.
        
        Args:
            title (str): Title of the spreadsheet
            
        Returns:
            Dict: Created spreadsheet metadata
        """
        try:
            spreadsheet = {
                'properties': {
                    'title': title
                }
            }
            
            created_spreadsheet = self.service.spreadsheets().create(
                body=spreadsheet
            ).execute()
            
            return created_spreadsheet
        except Exception as e:
            logger.error(f"Error creating spreadsheet: {e}")
            raise
            
    def get_spreadsheet(self, spreadsheet_id: str) -> Dict:
        """
        Get a specific spreadsheet.
        
        Args:
            spreadsheet_id (str): ID of the spreadsheet to retrieve
            
        Returns:
            Dict: Spreadsheet metadata
        """
        try:
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()
            
            return spreadsheet
        except Exception as e:
            logger.error(f"Error getting spreadsheet: {e}")
            raise
            
    def update_values(self, spreadsheet_id: str, range_name: str, values: List[List[Any]]) -> Dict:
        """
        Update values in a spreadsheet.
        
        Args:
            spreadsheet_id (str): ID of the spreadsheet
            range_name (str): Range to update (e.g., 'Sheet1!A1:B2')
            values (List[List[Any]]): Values to write
            
        Returns:
            Dict: Update response
        """
        try:
            body = {
                'values': values
            }
            
            result = self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            return result
        except Exception as e:
            logger.error(f"Error updating values: {e}")
            raise
            
    def get_values(self, spreadsheet_id: str, range_name: str) -> List[List[Any]]:
        """
        Get values from a spreadsheet.
        
        Args:
            spreadsheet_id (str): ID of the spreadsheet
            range_name (str): Range to read (e.g., 'Sheet1!A1:B2')
            
        Returns:
            List[List[Any]]: Values from the range
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            return result.get('values', [])
        except Exception as e:
            logger.error(f"Error getting values: {e}")
            raise
            
    def append_values(self, spreadsheet_id: str, range_name: str, values: List[List[Any]]) -> Dict:
        """
        Append values to a spreadsheet.
        
        Args:
            spreadsheet_id (str): ID of the spreadsheet
            range_name (str): Range to append to (e.g., 'Sheet1!A:B')
            values (List[List[Any]]): Values to append
            
        Returns:
            Dict: Append response
        """
        try:
            body = {
                'values': values
            }
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            return result
        except Exception as e:
            logger.error(f"Error appending values: {e}")
            raise
            
    def batch_update(self, spreadsheet_id: str, requests: List[Dict]) -> Dict:
        """
        Perform a batch update on a spreadsheet.
        
        Args:
            spreadsheet_id (str): ID of the spreadsheet
            requests (List[Dict]): List of update requests
            
        Returns:
            Dict: Batch update response
        """
        try:
            body = {
                'requests': requests
            }
            
            result = self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()
            
            return result
        except Exception as e:
            logger.error(f"Error performing batch update: {e}")
            raise

    def create_workout_tracker(self, title: str) -> Dict[str, Any]:
        """Create a new workout tracking spreadsheet."""
        try:
            spreadsheet = {
                'properties': {
                    'title': title
                },
                'sheets': [
                    {
                        'properties': {
                            'title': 'Workouts',
                            'gridProperties': {
                                'rowCount': 1000,
                                'columnCount': 10
                            }
                        }
                    },
                    {
                        'properties': {
                            'title': 'Nutrition',
                            'gridProperties': {
                                'rowCount': 1000,
                                'columnCount': 10
                            }
                        }
                    }
                ]
            }
            
            created_spreadsheet = self.service.spreadsheets().create(
                body=spreadsheet
            ).execute()
            
            # Add headers to the Workouts sheet
            workout_headers = [
                ['Date', 'Workout Type', 'Duration', 'Calories Burned', 'Notes']
            ]
            self.update_values(
                created_spreadsheet['spreadsheetId'],
                'Workouts!A1:E1',
                workout_headers
            )
            
            # Add headers to the Nutrition sheet
            nutrition_headers = [
                ['Date', 'Meal', 'Calories', 'Protein (g)', 'Carbs (g)', 'Fat (g)', 'Notes']
            ]
            self.update_values(
                created_spreadsheet['spreadsheetId'],
                'Nutrition!A1:G1',
                nutrition_headers
            )
            
            return created_spreadsheet
        except Exception as e:
            logger.error(f"Error creating workout tracker: {e}")
            raise
            
    def add_workout_entry(self, spreadsheet_id: str, date: str, workout_type: str, 
                         duration: str, calories: str, notes: str = "") -> Dict[str, Any]:
        """
        Add a workout entry to the tracker.
        
        Args:
            spreadsheet_id (str): ID of the spreadsheet
            date (str): Date of the workout
            workout_type (str): Type of workout
            duration (str): Duration of the workout
            calories (str): Calories burned
            notes (str, optional): Additional notes
            
        Returns:
            Dict: Update response
        """
        try:
            values = [[date, workout_type, duration, calories, notes]]
            return self.append_values(spreadsheet_id, 'Workouts!A:E', values)
        except Exception as e:
            logger.error(f"Error adding workout entry: {e}")
            raise
            
    def add_nutrition_entry(self, spreadsheet_id: str, date: str, meal: str,
                           calories: str, protein: str, carbs: str, fat: str,
                           notes: str = "") -> Dict[str, Any]:
        """
        Add a nutrition entry to the tracker.
        
        Args:
            spreadsheet_id (str): ID of the spreadsheet
            date (str): Date of the meal
            meal (str): Type of meal
            calories (str): Calories consumed
            protein (str): Protein in grams
            carbs (str): Carbs in grams
            fat (str): Fat in grams
            notes (str, optional): Additional notes
            
        Returns:
            Dict: Update response
        """
        try:
            values = [[date, meal, calories, protein, carbs, fat, notes]]
            return self.append_values(spreadsheet_id, 'Nutrition!A:G', values)
        except Exception as e:
            logger.error(f"Error adding nutrition entry: {e}")
            raise
            
    def get_workout_history(self, spreadsheet_id: str) -> List[List[str]]:
        """
        Get workout history from the tracker.
        
        Args:
            spreadsheet_id (str): ID of the spreadsheet
            
        Returns:
            List[List[str]]: Workout history
        """
        try:
            return self.get_values(spreadsheet_id, 'Workouts!A2:E')
        except Exception as e:
            logger.error(f"Error getting workout history: {e}")
            raise
            
    def get_nutrition_history(self, spreadsheet_id: str) -> List[List[str]]:
        """
        Get nutrition history from the tracker.
        
        Args:
            spreadsheet_id (str): ID of the spreadsheet
            
        Returns:
            List[List[str]]: Nutrition history
        """
        try:
            return self.get_values(spreadsheet_id, 'Nutrition!A2:G')
        except Exception as e:
            logger.error(f"Error getting nutrition history: {e}")
            raise
            
    def create_workout_summary(self, spreadsheet_id: str) -> Dict[str, Any]:
        """
        Create a summary sheet with workout statistics.
        
        Args:
            spreadsheet_id (str): ID of the spreadsheet
            
        Returns:
            Dict: Update response
        """
        try:
            # Create a new sheet for the summary
            requests = [{
                'addSheet': {
                    'properties': {
                        'title': 'Summary',
                        'gridProperties': {
                            'rowCount': 100,
                            'columnCount': 10
                        }
                    }
                }
            }]
            
            self.batch_update(spreadsheet_id, requests)
            
            # Add summary headers
            summary_headers = [
                ['Workout Summary'],
                ['Total Workouts', 'Total Duration', 'Total Calories Burned', 'Average Duration', 'Average Calories'],
                ['Nutrition Summary'],
                ['Total Meals', 'Total Calories', 'Average Protein', 'Average Carbs', 'Average Fat']
            ]
            
            self.update_values(spreadsheet_id, 'Summary!A1:E4', summary_headers)
            
            # Get workout data
            workouts = self.get_workout_history(spreadsheet_id)
            total_workouts = len(workouts)
            total_duration = sum(float(w[2]) for w in workouts if w[2].isdigit())
            total_calories = sum(float(w[3]) for w in workouts if w[3].isdigit())
            avg_duration = total_duration / total_workouts if total_workouts > 0 else 0
            avg_calories = total_calories / total_workouts if total_workouts > 0 else 0
            
            # Get nutrition data
            nutrition = self.get_nutrition_history(spreadsheet_id)
            total_meals = len(nutrition)
            total_nutrition_calories = sum(float(n[2]) for n in nutrition if n[2].isdigit())
            avg_protein = sum(float(n[3]) for n in nutrition if n[3].isdigit()) / total_meals if total_meals > 0 else 0
            avg_carbs = sum(float(n[4]) for n in nutrition if n[4].isdigit()) / total_meals if total_meals > 0 else 0
            avg_fat = sum(float(n[5]) for n in nutrition if n[5].isdigit()) / total_meals if total_meals > 0 else 0
            
            # Update summary values
            summary_values = [
                [str(total_workouts), f"{total_duration:.1f}", f"{total_calories:.1f}", f"{avg_duration:.1f}", f"{avg_calories:.1f}"],
                ['', '', '', '', ''],
                [str(total_meals), f"{total_nutrition_calories:.1f}", f"{avg_protein:.1f}", f"{avg_carbs:.1f}", f"{avg_fat:.1f}"]
            ]
            
            return self.update_values(spreadsheet_id, 'Summary!A2:E4', summary_values)
        except Exception as e:
            logger.error(f"Error creating workout summary: {e}")
            raise

    def authenticate(self):
        # Already authenticated in base class
        pass

    def get_sheet_data(self, spreadsheet_id: str, range_name: str) -> List[List[Any]]:
        """
        Get data from a specific range in the spreadsheet.
        
        Args:
            spreadsheet_id (str): ID of the spreadsheet
            range_name (str): Range to read (e.g., 'Sheet1!A1:B2')
            
        Returns:
            List[List[Any]]: Values from the range
        """
        try:
            return self.get_values(spreadsheet_id, range_name)
        except Exception as e:
            logger.error(f"Error getting sheet data: {e}")
            raise 