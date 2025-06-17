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
import asyncio

logger = logging.getLogger(__name__)

class GoogleTasksService(GoogleServiceBase):
    """Service for interacting with Google Tasks API."""
    
    def __init__(self):
        """Initialize the Tasks service."""
        self.SCOPES = ['https://www.googleapis.com/auth/tasks.readonly']
        super().__init__()
        # Note: authenticate() is now async, but __init__ cannot be async
        # We'll handle authentication in initialize_service instead
        
    async def initialize_service(self):
        """Initialize the Google Tasks service."""
        # Don't call authenticate() here - it's handled by the base class
        return build('tasks', 'v1', credentials=self.creds)
        
    async def list_tasklists(self) -> List[Dict]:
        """Asynchronously list all task lists."""
        try:
            def fetch():
                results = self.service.tasklists().list().execute()
                return results.get('items', [])
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error listing task lists: {e}")
            raise
            
    async def get_tasklist(self, tasklist_id: str) -> Dict:
        """Asynchronously get a specific task list."""
        try:
            def fetch():
                tasklist = self.service.tasklists().get(tasklistId=tasklist_id).execute()
                return tasklist
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error getting task list: {e}")
            raise
            
    async def create_tasklist(self, title: str) -> Dict:
        """Asynchronously create a new task list."""
        try:
            def create():
                tasklist = self.service.tasklists().insert(
                    body={'title': title}
                ).execute()
                return tasklist
            return await asyncio.to_thread(create)
        except Exception as e:
            logger.error(f"Error creating task list: {e}")
            raise
            
    async def list_tasks(self, tasklist_id: str, show_completed: bool = False) -> List[Dict]:
        """Asynchronously list tasks in a task list."""
        try:
            def fetch():
                results = self.service.tasks().list(
                    tasklist=tasklist_id,
                    showCompleted=show_completed
                ).execute()
                return results.get('items', [])
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error listing tasks: {e}")
            raise
            
    async def create_task(self, tasklist_id: str, title: str, notes: Optional[str] = None, due: Optional[Union[datetime, str]] = None) -> Dict:
        """Asynchronously create a new task."""
        try:
            def create():
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
            return await asyncio.to_thread(create)
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            raise
            
    async def update_task(self, tasklist_id: str, task_id: str, title: Optional[str] = None, notes: Optional[str] = None, 
                   due: Optional[datetime] = None, status: Optional[str] = None) -> Dict:
        """Asynchronously update an existing task."""
        try:
            def update():
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
            return await asyncio.to_thread(update)
        except Exception as e:
            logger.error(f"Error updating task: {e}")
            raise
            
    async def delete_task(self, tasklist_id: str, task_id: str) -> None:
        """Asynchronously delete a task."""
        try:
            def delete():
                self.service.tasks().delete(
                    tasklist=tasklist_id,
                    task=task_id
                ).execute()
            await asyncio.to_thread(delete)
        except Exception as e:
            logger.error(f"Error deleting task: {e}")
            raise

    async def create_workout_tasklist(self) -> Dict:
        """Asynchronously create a new task list specifically for workout goals."""
        try:
            def create():
                tasklist = {
                    'title': 'Workout Tasks'
                }
                result = self.service.tasklists().insert(body=tasklist).execute()
                return result
            return await asyncio.to_thread(create)
        except Exception as e:
            logger.error(f"Error creating workout task list: {e}")
            raise

    async def add_workout_task(self, tasklist_id: str, workout_name: str, notes: Optional[str] = None, 
                        due_date: Optional[datetime] = None) -> Dict:
        """Asynchronously add a new workout task to a task list."""
        try:
            def create():
                task = {
                    'title': workout_name
                }
                
                if notes:
                    task['notes'] = notes
                if due_date:
                    task['due'] = due_date.isoformat()
                    
                created_task = self.service.tasks().insert(
                    tasklist=tasklist_id,
                    body=task
                ).execute()
                
                return created_task
            return await asyncio.to_thread(create)
        except Exception as e:
            logger.error(f"Error adding workout task: {e}")
            raise

    async def get_workout_tasks(self, tasklist_id: str, show_completed: bool = False) -> List[Dict]:
        """Asynchronously get all workout tasks from a task list."""
        try:
            return await self.list_tasks(tasklist_id, show_completed)
        except Exception as e:
            logger.error(f"Error getting workout tasks: {e}")
            raise

    async def get_tasks(self, tasklist_id: str = '@default', query: str = None) -> List[Dict[str, Any]]:
        """Asynchronously get tasks from the user's task lists."""
        try:
            def fetch():
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
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error fetching tasks: {str(e)}")
            raise 