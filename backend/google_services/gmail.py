from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from typing import List, Dict, Any
import logging
from backend.google_services.base import GoogleServiceBase
from backend.google_services.auth import get_google_credentials
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import base64
import asyncio

logger = logging.getLogger(__name__)

class GoogleGmailService(GoogleServiceBase):
    """Service for interacting with Gmail API."""
    
    def __init__(self):
        """Initialize the Gmail service."""
        self.SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
        super().__init__()

    async def initialize_service(self):
        """Initialize the Google Gmail service using the new OAuth flow."""
        return build('gmail', 'v1', credentials=self.creds)

    async def get_recent_emails(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """Asynchronously get recent emails from the user's Gmail."""
        try:
            def fetch_emails():
                results = self.service.users().messages().list(
                    userId='me',
                    maxResults=max_results
                ).execute()
                messages = results.get('messages', [])
                emails = []
                for message in messages:
                    msg = self.service.users().messages().get(
                        userId='me',
                        id=message['id']
                    ).execute()
                    headers = msg['payload']['headers']
                    subject = next(h['value'] for h in headers if h['name'] == 'Subject')
                    sender = next(h['value'] for h in headers if h['name'] == 'From')
                    emails.append({
                        'id': message['id'],
                        'subject': subject,
                        'sender': sender,
                        'snippet': msg['snippet']
                    })
                return emails
            return await asyncio.to_thread(fetch_emails)
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            raise

    def search_emails(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for emails matching a specific query."""
        try:
            # Convert natural language query to Gmail search syntax if needed
            if 'this week' in query.lower():
                query = f"{query} after:{datetime.now().strftime('%Y/%m/%d')}"
            elif 'last week' in query.lower():
                last_week = datetime.now() - timedelta(days=7)
                query = f"{query} after:{last_week.strftime('%Y/%m/%d')} before:{datetime.now().strftime('%Y/%m/%d')}"
            elif 'this month' in query.lower():
                query = f"{query} after:{datetime.now().strftime('%Y/%m/01')}"
            elif 'last month' in query.lower():
                last_month = datetime.now() - timedelta(days=30)
                query = f"{query} after:{last_month.strftime('%Y/%m/01')} before:{datetime.now().strftime('%Y/%m/01')}"

            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            messages = results.get('messages', [])
            
            emails = []
            for message in messages:
                msg = self.service.users().messages().get(
                    userId='me',
                    id=message['id']
                ).execute()
                
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
                
                emails.append({
                    'id': message['id'],
                    'subject': subject,
                    'sender': sender,
                    'snippet': msg['snippet']
                })
            
            return emails
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            raise

    async def get_email_content(self, message_id):
        """Asynchronously get the content of a specific email."""
        try:
            def fetch():
                message = self.service.users().messages().get(
                    userId='me',
                    id=message_id,
                    format='full'
                ).execute()
                
                # Extract the email content
                if 'payload' in message:
                    payload = message['payload']
                    if 'parts' in payload:
                        # Multipart message
                        for part in payload['parts']:
                            if part['mimeType'] == 'text/plain':
                                data = part['body'].get('data', '')
                                if data:
                                    return base64.urlsafe_b64decode(data).decode('utf-8')
                    else:
                        # Simple message
                        data = payload['body'].get('data', '')
                        if data:
                            return base64.urlsafe_b64decode(data).decode('utf-8')
                
                return "No content found"
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error getting email content: {e}")
            raise

    def list_messages(self, query: str = '', max_results: int = 10) -> List[Dict]:
        """
        List messages in the user's mailbox.
        
        Args:
            query (str): Search query to filter messages
            max_results (int): Maximum number of messages to return
            
        Returns:
            List[Dict]: List of message metadata
        """
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            return messages
        except Exception as e:
            logger.error(f"Error listing messages: {e}")
            raise
            
    async def get_message(self, message_id: str) -> Dict:
        """Asynchronously get a specific message by ID."""
        try:
            def fetch():
                return self.service.users().messages().get(
                    userId='me',
                    id=message_id
                ).execute()
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.error(f"Error getting message: {e}")
            raise
            
    def send_message(self, to: str, subject: str, body: str, is_html: bool = False) -> Dict:
        """
        Send an email message.
        
        Args:
            to (str): Recipient email address
            subject (str): Email subject
            body (str): Email body
            is_html (bool): Whether the body is HTML
            
        Returns:
            Dict: Sent message data
        """
        try:
            message = MIMEMultipart()
            message['to'] = to
            message['subject'] = subject
            
            # Attach the body
            if is_html:
                msg = MIMEText(body, 'html')
            else:
                msg = MIMEText(body)
            message.attach(msg)
            
            # Encode the message
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Send the message
            sent_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()
            
            return sent_message
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise
            
    async def create_draft(self, to: str, subject: str, body: str, is_html: bool = False) -> Dict:
        """Asynchronously create a draft email message."""
        try:
            def create():
                message = MIMEMultipart()
                message['to'] = to
                message['subject'] = subject
                if is_html:
                    msg = MIMEText(body, 'html')
                else:
                    msg = MIMEText(body)
                message.attach(msg)
                raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
                draft = self.service.users().drafts().create(
                    userId='me',
                    body={'message': {'raw': raw}}
                ).execute()
                return draft
            return await asyncio.to_thread(create)
        except Exception as e:
            logger.error(f"Error creating draft: {e}")
            raise

    def modify_message_labels(self, message_id: str, add_labels: List[str] = None, remove_labels: List[str] = None) -> Dict:
        """
        Modify the labels of a message.
        
        Args:
            message_id (str): ID of the message to modify
            add_labels (List[str]): Labels to add
            remove_labels (List[str]): Labels to remove
            
        Returns:
            Dict: Modified message data
        """
        try:
            body = {}
            if add_labels:
                body['addLabelIds'] = add_labels
            if remove_labels:
                body['removeLabelIds'] = remove_labels
                
            message = self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body=body
            ).execute()
            
            return message
        except Exception as e:
            logger.error(f"Error modifying message labels: {e}")
            raise 