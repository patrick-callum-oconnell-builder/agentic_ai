import os
import logging
from typing import Optional, List
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from abc import ABC, abstractmethod
from backend.google_services.auth import get_google_credentials

# Configure logger
logger = logging.getLogger(__name__)

class GoogleServiceBase(ABC):
    """Base class for Google API services."""
    
    def __init__(self):
        """Initialize the service."""
        logger.debug("Initializing GoogleServiceBase...")
        self.creds = None
        self.service = None
        logger.debug("GoogleServiceBase initialized")

    @abstractmethod
    def initialize_service(self):
        """Initialize the Google service."""
        pass

    def authenticate(self):
        """Authenticate with Google API."""
        try:
            logger.info("Authenticating with Google API...")
            self.creds = get_google_credentials()
            logger.debug("Credentials obtained successfully")
            self.service = self.initialize_service()
            logger.info("Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to authenticate with Google API: {str(e)}", exc_info=True)
            raise

    def __del__(self):
        """Cleanup when the service is destroyed."""
        logger.debug("Cleaning up GoogleServiceBase...")
        if hasattr(self, 'service') and self.service is not None:
            try:
                logger.debug("Closing service connection...")
                self.service.close()
                logger.debug("Service connection closed successfully")
            except Exception as e:
                logger.warning(f"Error closing service: {str(e)}", exc_info=True)
        self.service = None
        self.creds = None
        logger.debug("GoogleServiceBase cleanup completed")

class GoogleAPIService:
    """Base class for Google API services that use API keys."""
    
    def __init__(self, api_key_env_var: str):
        """Initialize the service with an API key."""
        self.api_key = os.getenv(api_key_env_var)
        if not self.api_key:
            raise ValueError(f"{api_key_env_var} environment variable not set")
        self.service = None

    def __del__(self):
        """Cleanup when the service is destroyed."""
        try:
            if hasattr(self, 'service') and self.service is not None:
                # Only try to close if the service has a close method
                if hasattr(self.service, 'close'):
                    self.service.close()
                self.service = None
        except Exception as e:
            logger.error(f"Error closing service: {e}") 