import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from auth import authenticate_all_services, check_authentication_status, ensure_adc


def main():
    print("Google API Authentication Setup")
    print("===============================\n")

    # Ensure ADC is set up before proceeding
    if not ensure_adc():
        print("\n[!] Could not set up Application Default Credentials (ADC). Aborting setup.")
        return

    # Check if required environment variables are set
    required_vars = ['GOOGLE_CLIENT_ID', 'GOOGLE_PROJECT_ID', 'GOOGLE_CLIENT_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print("Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"- {var}")
        print("\nPlease set these variables in your .env file in the backend directory.")
        return

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

if __name__ == "__main__":
    main() 