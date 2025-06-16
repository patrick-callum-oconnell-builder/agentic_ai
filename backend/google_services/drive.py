from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from typing import List, Dict, Any, Optional
import logging
from backend.google_services.base import GoogleServiceBase
from backend.google_services.auth import get_google_credentials

logger = logging.getLogger(__name__)

class GoogleDriveService(GoogleServiceBase):
    """Service for interacting with Google Drive API."""
    
    def __init__(self):
        """Initialize the Google Drive service."""
        self.SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        self.creds = None
        self.service = self.initialize_service()
        
    def initialize_service(self):
        """Initialize the Google Drive service using the new OAuth flow."""
        self.creds = get_google_credentials()
        return build('drive', 'v3', credentials=self.creds)
        
    def authenticate(self):
        # Already authenticated in base class
        pass
        
    def list_files(self, query: str = '', max_results: int = 10) -> List[Dict]:
        """
        List files in the user's Drive.
        
        Args:
            query (str): Search query to filter files
            max_results (int): Maximum number of files to return
            
        Returns:
            List[Dict]: List of file metadata
        """
        try:
            results = self.service.files().list(
                q=query,
                pageSize=max_results,
                fields="nextPageToken, files(id, name, mimeType)"
            ).execute()
            
            return results.get('files', [])
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            raise
            
    def get_file(self, file_id: str) -> Dict:
        """
        Get a specific file by ID.
        
        Args:
            file_id (str): ID of the file to retrieve
            
        Returns:
            Dict: File metadata
        """
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size, createdTime, modifiedTime"
            ).execute()
            
            return file
        except Exception as e:
            logger.error(f"Error getting file: {e}")
            raise
            
    def create_folder(self, folder_name: str) -> Dict[str, Any]:
        """Create a folder in Google Drive."""
        try:
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            return folder
        except Exception as e:
            logger.error(f"Error creating folder: {e}")
            return {}
            
    def create_workout_folder(self, name: str = 'Workout Plans', parent_id: Optional[str] = None) -> Dict:
        """
        Alias for create_folder to create a workout folder. Default name is 'Workout Plans'.
        """
        return self.create_folder(name=name)
            
    def upload_file(self, file_path: str, name: Optional[str] = None, parent_id: Optional[str] = None) -> Dict:
        """
        Upload a file to Drive.
        
        Args:
            file_path (str): Path to the file to upload
            name (str, optional): Name to give the file in Drive
            parent_id (str, optional): ID of the parent folder
            
        Returns:
            Dict: Uploaded file metadata
        """
        try:
            file_metadata = {}
            if name:
                file_metadata['name'] = name
            if parent_id:
                file_metadata['parents'] = [parent_id]
                
            media = self.service.files().create(
                body=file_metadata,
                media_body=file_path,
                fields='id, name, mimeType'
            ).execute()
            
            return media
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise
            
    def delete_file(self, file_id: str) -> None:
        """
        Delete a file from Drive.
        
        Args:
            file_id (str): ID of the file to delete
        """
        try:
            self.service.files().delete(fileId=file_id).execute()
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            raise

    def get_recent_files(self, max_results: int = 10) -> List[Dict[str, Any]]:
        try:
            results = self.service.files().list(
                pageSize=max_results,
                orderBy='modifiedTime desc',
                fields='files(id, name, mimeType, modifiedTime)'
            ).execute()
            
            return results.get('files', [])
        except Exception as e:
            logger.error(f"Error fetching recent files: {e}")
            return [] 