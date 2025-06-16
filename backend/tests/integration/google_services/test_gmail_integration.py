import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.integration.google_services.base_google_integration import BaseGoogleIntegrationTest
from agent import PersonalTrainerAgent
from google_services.gmail import GoogleGmailService

class TestGmailIntegration(BaseGoogleIntegrationTest):
    """Test suite for Google Gmail integration."""
    
    def test_get_recent_emails(self):
        """Test fetching recent emails."""
        try:
            # Fetch recent emails using the agent's gmail service
            emails = self.agent.gmail_service.get_recent_emails()
            self.assertIsInstance(emails, list)
            print(f"Gmail test: Successfully fetched {len(emails)} emails")
        except Exception as e:
            self.fail(f"Failed to fetch emails: {str(e)}")

if __name__ == '__main__':
    unittest.main() 