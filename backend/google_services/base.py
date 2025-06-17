import os
import logging
import asyncio
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
    async def initialize_service(self):
        """Initialize the Google service."""
        pass

    async def authenticate(self):
        """Authenticate with Google API."""
        try:
            logger.info("Authenticating with Google API...")
            self.creds = get_google_credentials()
            logger.debug("Credentials obtained successfully")
            self.service = await self.initialize_service()
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
    """Base class for Google API services."""
    
    def __init__(self, api_key_env_var: str):
        """Initialize the service with API key from environment variable."""
        logger.debug(f"Initializing GoogleAPIService with API key from {api_key_env_var}...")
        # Check if api_key_env_var is actually an API key (starts with AIza)
        if api_key_env_var.startswith('AIza'):
            self.api_key = api_key_env_var
        else:
            self.api_key = os.getenv(api_key_env_var)
            if not self.api_key:
                logger.error(f"API key not set in environment variable {api_key_env_var}")
                raise ValueError(f"API key not set in environment variable {api_key_env_var}.")
        logger.debug("API key loaded successfully") 