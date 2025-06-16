import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import pickle
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define the scopes for each service
SCOPES = {
    'calendar': ['https://www.googleapis.com/auth/calendar.readonly'],
    'gmail': ['https://www.googleapis.com/auth/gmail.readonly'],
    'fitness': [
        'https://www.googleapis.com/auth/fitness.activity.read',
        'https://www.googleapis.com/auth/fitness.body.read',
        'https://www.googleapis.com/auth/fitness.sleep.read'
    ],
    'tasks': ['https://www.googleapis.com/auth/tasks'],
    'drive': ['https://www.googleapis.com/auth/drive.file'],
    'sheets': ['https://www.googleapis.com/auth/spreadsheets']
}

def get_credentials(service_name: str) -> Credentials:
    """Get credentials for a specific service."""
    creds = None
    token_file = f'{service_name}_token.pickle'

    # Load existing token if available
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)

    # If no valid credentials available, let's create them
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Create credentials from environment variables
            client_config = {
                "installed": {
                    "client_id": os.getenv('GOOGLE_CLIENT_ID'),
                    "project_id": os.getenv('GOOGLE_PROJECT_ID'),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
                    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
                }
            }
            
            flow = InstalledAppFlow.from_client_config(
                client_config, SCOPES[service_name])
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)

    return creds

def authenticate_all_services():
    """Authenticate all services and return their credentials."""
    credentials = {}
    for service in SCOPES.keys():
        try:
            credentials[service] = get_credentials(service)
        except Exception as e:
            print(f"Error authenticating {service}: {str(e)}")
    return credentials

def check_authentication_status():
    """Check which services have been authenticated."""
    status = {}
    for service in SCOPES.keys():
        token_file = f'{service}_token.pickle'
        status[service] = os.path.exists(token_file)
    return status

if __name__ == '__main__':
    print("Google API Authentication Setup")
    print("===============================\n")
    
    # Check if environment variables are set
    required_vars = ['GOOGLE_CLIENT_ID', 'GOOGLE_PROJECT_ID', 'GOOGLE_CLIENT_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"- {var}")
        print("\nPlease set these variables in your .env file")
        exit(1)
    
    print("Checking current authentication status...\n")
    status = check_authentication_status()
    
    print("Current authentication status:")
    for service, is_authenticated in status.items():
        print(f"- {service}: {'✓' if is_authenticated else '✗'}")
    
    print("\nStarting authentication process...")
    print("A browser window will open for each service that needs authentication.")
    print("Please follow the prompts to authorize the application.\n")
    print("Note: You may need to authorize multiple times as each service requires its own permissions.\n")
    
    input("Press Enter to continue...")
    
    credentials = authenticate_all_services()
    
    print("\nFinal authentication status:")
    for service, is_authenticated in check_authentication_status().items():
        print(f"- {service}: {'✓' if is_authenticated else '✗'}")
    
    if not all(check_authentication_status().values()):
        print("\n⚠ Some services failed to authenticate. Please check the error messages above.")
        print("You can run this script again to retry the authentication process.") 