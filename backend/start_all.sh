#!/bin/bash

# Function to check if a port is in use
check_port() {
    if lsof -i :$1 > /dev/null; then
        echo "Port $1 is already in use. Do you want to kill the process using it? (y/n)"
        read -r answer
        if [[ "$answer" == "y" ]]; then
            lsof -ti :$1 | xargs kill -9
            echo "Process killed. Continuing..."
        else
            echo "Exiting..."
            exit 1
        fi
    fi
}

# Function to check if an environment variable is set
check_env_var() {
    if [ -z "${!1}" ]; then
        echo "Error: $1 is not set. Please set it in your environment or .env file."
        echo "Example: export $1='your-value'"
        exit 1
    fi
}

# Debug: Print current directory and check if .env exists
echo "Current directory: $(pwd)"
echo "Checking for .env file..."
if [ -f ".env" ]; then
    echo ".env file found"
    echo "Loading .env file..."
    set -a
    source .env
    set +a
else
    echo "Warning: .env file not found in current directory"
fi

# Debug: Print environment variable status
echo "Environment variable status:"
echo "GOOGLE_CLIENT_ID: ${GOOGLE_CLIENT_ID:+set}"
echo "GOOGLE_CLIENT_SECRET: ${GOOGLE_CLIENT_SECRET:+set}"
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:+set}"
echo "GOOGLE_MAPS_API_KEY: ${GOOGLE_MAPS_API_KEY:+set}"

# Check required environment variables
echo "Checking environment variables..."
check_env_var "GOOGLE_CLIENT_ID"
check_env_var "GOOGLE_CLIENT_SECRET"
check_env_var "OPENAI_API_KEY"

# Optional environment variables
if [ -z "$GOOGLE_MAPS_API_KEY" ]; then
    echo "Warning: GOOGLE_MAPS_API_KEY is not set. Maps features will be disabled."
fi

# Check if backend port (8000) is in use
check_port 8000

# Start backend (FastAPI, uvicorn, port 8000)
echo "Starting backend on http://localhost:8000 ..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000 --log-level debug > backend.log 2>&1 &
BACKEND_PID=$!
tail -f backend.log &
TAIL_PID=$!

# Check if frontend port (3000) is in use
check_port 3000

# Start frontend (React, npm, port 3000)
echo "Starting frontend on http://localhost:3000 ..."
cd ../frontend
npm install
npm start &
FRONTEND_PID=$!
cd ..

# Wait for user to press Ctrl+C, then kill all servers
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID $TAIL_PID" SIGINT
wait

# Add debug output
echo "DEBUG: PATH is set to $PATH"
echo "DEBUG: which node returns $(which node)"

check_python_version() {
    local version_string
    if [[ -n "$PYTHON_VERSION" ]]; then
        version_string="$PYTHON_VERSION"
        echo "DEBUG: Using PYTHON_VERSION from env: $version_string"
    else
        version_string=$(python3 --version 2>&1 | awk '{print $2}')
        echo "DEBUG: Using python3 --version: $version_string"
    fi
    required="3.8.0"
    # Compare versions using sort -V
    if [[ "$(printf '%s\n' "$required" "$version_string" | sort -V | head -n1)" != "$required" ]]; then
        echo -e "\033[0;31mError: Python 3.8 or higher is required. Found version $version_string\033[0m"
        exit 1
    fi
} 