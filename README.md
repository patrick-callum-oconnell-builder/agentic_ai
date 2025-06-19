# AI Personal Trainer

An AI-powered personal trainer application that helps users with their fitness goals (scheduling workouts in their calendar, meal-prepping, etc). The application integrates with Google cloud services so the agent can automate the work associated with these tasks and save the user time.

Here is a video demo of some functionality (in case you don't want to set up all of the Google Service API enabling, which isn't yet automated): 
https://drive.google.com/file/d/10pUME3WR3DRclbFq2YwOQmOTCEIaif9s/view?usp=sharing 

## Features

- Real-time conversation with the AI personal trainer.
- Integration with Google Calendar, Gmail, Google Maps, Google Drive, etc. 
- AI-powered workout suggestions and fitness advice that is context-aware relative to the data corpus provided in the chat and across the Google services.

## Architecture / Frameworks

Built with a modern Python FastAPI backend, LangGraph agent orchestration, and a React/MUI frontend for a clean, interactive user experience.

The agent's orchestration is based on a typical state-based transition logic to help it decide whether to chat, use a tool,
record preferences to memory, etc.

The full memory architecture is not implemented yet (more comprehensive memory than just the current KG), but will be completed in an update that is being developed!

## Prerequisites

- Python 3.8+
- Node.js 14+
- Google Cloud Platform account with Calendar and Gmail APIs enabled (as well as any other Google services you'd like to use)
- OpenAI API key

## Setup

### Backend Setup

1. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install the required packages:
```bash
cd backend
pip install -r requirements.txt
```

3. Set up Google Cloud credentials:
   - Go to the Google Cloud Console
   - Create a new project
   - Enable the Google Calendar and Gmail APIs
   - Create OAuth 2.0 credentials
   - Get your client ID and client secret from the OAuth 2.0 credentials page

4. Set up environment variables:
```bash
export OPENAI_API_KEY='your-openai-api-key'
export GOOGLE_CLIENT_ID='your-google-client-id'
export GOOGLE_CLIENT_SECRET='your-google-client-secret'
export GOOGLE_MAPS_API_KEY='your-google-maps-api-key'  # Optional, for location features
```

5. Start the backend server:
```bash
python main.py
```

### Frontend Setup

1. Install the required packages:
```bash
cd frontend
npm install
```

2. Start the development server:
```bash
npm start
```

## Usage

1. Open your browser and navigate to `http://localhost:3000`
2. The first time you use the application, you'll need to authenticate with Google
3. Start chatting with your AI personal trainer!

## API Endpoints

- `POST /api/chat`: Send messages to the AI personal trainer
- `GET /api/health`: Check the health status of the backend

## Contributing

Feel free to submit issues and enhancement requests! 