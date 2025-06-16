from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from typing import List, Dict, Any, Optional, Union
import logging
from datetime import datetime, timedelta
from backend.google_services.base import GoogleServiceBase

logger = logging.getLogger(__name__)

class GoogleTasksService(GoogleServiceBase):
    """Service for interacting with Google Tasks API."""
    
    def __init__(self):
        """Initialize the Tasks service."""
        self.SCOPES = ['https://www.googleapis.com/auth/tasks.readonly']
        super().__init__()
        self.authenticate()
        
    def initialize_service(self):
        """Initialize the Google Tasks service."""
        return build('tasks', 'v1', credentials=self.creds)
        
    def list_tasklists(self) -> List[Dict]:
        """
        List all task lists.
        
        Returns:
            List[Dict]: List of task list metadata
        """
        try:
            results = self.service.tasklists().list().execute()
            return results.get('items', [])
        except Exception as e:
            logger.error(f"Error listing task lists: {e}")
            raise
            
    def get_tasklist(self, tasklist_id: str) -> Dict:
        """
        Get a specific task list.
        
        Args:
            tasklist_id (str): ID of the task list to retrieve
            
        Returns:
            Dict: Task list metadata
        """
        try:
            tasklist = self.service.tasklists().get(tasklistId=tasklist_id).execute()
            return tasklist
        except Exception as e:
            logger.error(f"Error getting task list: {e}")
            raise
            
    def create_tasklist(self, title: str) -> Dict:
        """
        Create a new task list.
        
        Args:
            title (str): Title of the task list
            
        Returns:
            Dict: Created task list metadata
        """
        try:
            tasklist = self.service.tasklists().insert(
                body={'title': title}
            ).execute()
            return tasklist
        except Exception as e:
            logger.error(f"Error creating task list: {e}")
            raise
            
    def list_tasks(self, tasklist_id: str, show_completed: bool = False) -> List[Dict]:
        """
        List tasks in a task list.
        
        Args:
            tasklist_id (str): ID of the task list
            show_completed (bool): Whether to show completed tasks
            
        Returns:
            List[Dict]: List of task metadata
        """
        try:
            results = self.service.tasks().list(
                tasklist=tasklist_id,
                showCompleted=show_completed
            ).execute()
            return results.get('items', [])
        except Exception as e:
            logger.error(f"Error listing tasks: {e}")
            raise
            
    def create_task(self, tasklist_id: str, title: str, notes: Optional[str] = None, due: Optional[Union[datetime, str]] = None) -> Dict:
        """
        Create a new task.
        
        Args:
            tasklist_id (str): ID of the task list
            title (str): Title of the task
            notes (str, optional): Notes for the task
            due (Union[datetime, str], optional): Due date for the task (datetime object or RFC3339 string)
            
        Returns:
            Dict: Created task metadata
        """
        try:
            task = {
                'title': title
            }
            
            if notes:
                task['notes'] = notes
            if due:
                if isinstance(due, datetime):
                    task['due'] = due.isoformat()
                else:
                    task['due'] = due
                
            created_task = self.service.tasks().insert(
                tasklist=tasklist_id,
                body=task
            ).execute()
            
            return created_task
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            raise
            
    def update_task(self, tasklist_id: str, task_id: str, title: Optional[str] = None, notes: Optional[str] = None, 
                   due: Optional[datetime] = None, status: Optional[str] = None) -> Dict:
        """
        Update an existing task.
        
        Args:
            tasklist_id (str): ID of the task list
            task_id (str): ID of the task to update
            title (str, optional): New title for the task
            notes (str, optional): New notes for the task
            due (datetime, optional): New due date for the task
            status (str, optional): New status for the task ('needsAction' or 'completed')
            
        Returns:
            Dict: Updated task metadata
        """
        try:
            task = {}
            
            if title:
                task['title'] = title
            if notes:
                task['notes'] = notes
            if due:
                task['due'] = due.isoformat()
            if status:
                task['status'] = status
                
            updated_task = self.service.tasks().update(
                tasklist=tasklist_id,
                task=task_id,
                body=task
            ).execute()
            
            return updated_task
        except Exception as e:
            logger.error(f"Error updating task: {e}")
            raise
            
    def delete_task(self, tasklist_id: str, task_id: str) -> None:
        """
        Delete a task.
        
        Args:
            tasklist_id (str): ID of the task list
            task_id (str): ID of the task to delete
        """
        try:
            self.service.tasks().delete(
                tasklist=tasklist_id,
                task=task_id
            ).execute()
        except Exception as e:
            logger.error(f"Error deleting task: {e}")
            raise

    def create_workout_tasklist(self) -> Dict:
        """
        Create a new task list specifically for workout goals.
        
        Returns:
            Dict: Created task list metadata
        """
        try:
            tasklist = {
                'title': 'Workout Tasks'
            }
            result = self.service.tasklists().insert(body=tasklist).execute()
            return result
        except Exception as e:
            logger.error(f"Error creating workout task list: {e}")
            raise

    def add_workout_task(self, tasklist_id: str, workout_name: str, notes: Optional[str] = None, 
                        due_date: Optional[datetime] = None) -> Dict:
        """
        Add a new workout task to a task list.
        
        Args:
            tasklist_id (str): ID of the task list
            workout_name (str): Name of the workout
            notes (str, optional): Additional notes about the workout
            due_date (datetime, optional): When the workout should be completed
            
        Returns:
            Dict: Created task metadata
        """
        try:
            return self.create_task(
                tasklist_id=tasklist_id,
                title=workout_name,
                notes=notes,
                due=due_date
            )
        except Exception as e:
            logger.error(f"Error adding workout task: {e}")
            raise

    def get_workout_tasks(self, tasklist_id: str, show_completed: bool = False) -> List[Dict]:
        """
        Get all workout tasks from a task list.
        
        Args:
            tasklist_id (str): ID of the task list
            show_completed (bool): Whether to show completed tasks
            
        Returns:
            List[Dict]: List of workout task metadata
        """
        try:
            return self.list_tasks(tasklist_id, show_completed)
        except Exception as e:
            logger.error(f"Error getting workout tasks: {e}")
            raise

    def get_tasks(self, tasklist_id: str = '@default', query: str = None) -> List[Dict[str, Any]]:
        """Get tasks from the user's task lists."""
        try:
            tasks = self.service.tasks().list(
                tasklist=tasklist_id,
                showCompleted=False,
                showHidden=False
            ).execute()
            
            items = tasks.get('items', [])
            
            if query:
                # Filter tasks based on natural language query
                if 'this week' in query.lower():
                    start_date = datetime.now()
                    end_date = start_date + timedelta(days=7)
                    items = [task for task in items if task.get('due') and start_date <= datetime.fromisoformat(task['due'].replace('Z', '+00:00')) <= end_date]
                elif 'this month' in query.lower():
                    start_date = datetime.now()
                    end_date = start_date + timedelta(days=30)
                    items = [task for task in items if task.get('due') and start_date <= datetime.fromisoformat(task['due'].replace('Z', '+00:00')) <= end_date]
                elif 'overdue' in query.lower():
                    now = datetime.now()
                    items = [task for task in items if task.get('due') and datetime.fromisoformat(task['due'].replace('Z', '+00:00')) < now]
            
            return items
        except Exception as e:
            print(f"Error fetching tasks: {str(e)}")
            return [] 