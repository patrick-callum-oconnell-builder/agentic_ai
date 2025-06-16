import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router, initialize_services

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)
logger = logging.getLogger(__name__)

# Log environment variable status (without exposing values)
logger.info("Environment variables status:")
logger.info(f"GOOGLE_CLIENT_ID: {'Set' if os.getenv('GOOGLE_CLIENT_ID') else 'Not set'}")
logger.info(f"GOOGLE_CLIENT_SECRET: {'Set' if os.getenv('GOOGLE_CLIENT_SECRET') else 'Not set'}")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('backend.log')
    ]
)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include the router
app.include_router(router, prefix="/api")

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    logger.info("Starting application initialization...")
    try:
        await initialize_services()
        logger.info("Application initialization completed successfully")
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        logger.error("Please ensure you have set up the following environment variables:")
        logger.error("1. GOOGLE_CLIENT_ID")
        logger.error("2. GOOGLE_CLIENT_SECRET")
        logger.error("You can obtain these from the Google Cloud Console:")
        logger.error("1. Go to https://console.cloud.google.com")
        logger.error("2. Create a new project or select an existing one")
        logger.error("3. Enable the required APIs (Calendar, Gmail, Drive, Sheets, Fitness, Tasks)")
        logger.error("4. Create OAuth 2.0 credentials")
        raise

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting backend server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
