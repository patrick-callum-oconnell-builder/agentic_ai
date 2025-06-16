import os
import pickle
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Configure logger
logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
]

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), 'credentials.json')
TOKEN_PICKLE = os.path.join(os.path.dirname(__file__), "token.pickle")

def get_google_credentials():
    """Get Google API credentials using OAuth2 flow."""
    logger.info("Getting Google API credentials...")
    
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.error("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET environment variables")
        raise ValueError("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET environment variables.")

    creds = None
    # Load token if it exists
    if os.path.exists(TOKEN_PICKLE):
        logger.debug("Found existing token file, attempting to load...")
        try:
            with open(TOKEN_PICKLE, "rb") as token:
                creds = pickle.load(token)
            logger.debug("Successfully loaded existing token")
        except Exception as e:
            logger.warning(f"Error loading existing token: {str(e)}", exc_info=True)
            creds = None

    # If no valid creds, do OAuth2 flow
    if not creds or not creds.valid:
        logger.info("No valid credentials found, starting OAuth2 flow...")
        if creds and creds.expired and creds.refresh_token:
            logger.debug("Credentials expired, attempting to refresh...")
            try:
                creds.refresh(Request())
                logger.info("Successfully refreshed credentials")
            except Exception as e:
                logger.error(f"Error refreshing credentials: {str(e)}", exc_info=True)
                creds = None
        else:
            logger.debug("Starting new OAuth2 flow...")
            try:
                flow = InstalledAppFlow.from_client_config(
                    {
                        "installed": {
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "redirect_uris": [
                                "urn:ietf:wg:oauth:2.0:oob",
                                "http://localhost"
                            ]
                        }
                    },
                    scopes=SCOPES
                )
                logger.info("Starting local server for OAuth2 flow...")
                creds = flow.run_local_server(port=0)
                logger.info("Successfully obtained new credentials")
            except Exception as e:
                logger.error(f"Error during OAuth2 flow: {str(e)}", exc_info=True)
                raise

        # Save the credentials for next time
        try:
            logger.debug("Saving credentials to token file...")
            with open(TOKEN_PICKLE, "wb") as token:
                pickle.dump(creds, token)
            logger.debug("Successfully saved credentials")
        except Exception as e:
            logger.error(f"Error saving credentials: {str(e)}", exc_info=True)
            # Don't raise here, as we still have valid credentials in memory

    logger.info("Successfully obtained Google API credentials")
    return creds 