#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check required environment variables
check_env_vars() {
    local missing_vars=()
    
    # Check OAuth credentials
    if [ -z "$GOOGLE_CLIENT_ID" ]; then
        missing_vars+=("GOOGLE_CLIENT_ID")
    fi
    if [ -z "$GOOGLE_CLIENT_SECRET" ]; then
        missing_vars+=("GOOGLE_CLIENT_SECRET")
    fi
    
    # Check Maps API key
    if [ -z "$GOOGLE_MAPS_API_KEY" ]; then
        echo -e "${YELLOW}Warning: GOOGLE_MAPS_API_KEY is not set. Maps functionality will be limited.${NC}"
    fi
    
    # If any required vars are missing, show error and exit
    if [ ${#missing_vars[@]} -ne 0 ]; then
        echo -e "${RED}Error: The following required environment variables are not set:${NC}"
        printf '%s\n' "${missing_vars[@]}"
        echo -e "\nPlease set these variables in your environment or .env file"
        exit 1
    fi
}

# Function to check Python version
check_python_version() {
    if command_exists python3; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if (( $(echo "$PYTHON_VERSION < 3.8" | bc -l) )); then
            echo -e "${RED}Error: Python 3.8 or higher is required. Found version $PYTHON_VERSION${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Error: Python 3 is not installed${NC}"
        exit 1
    fi
}

# Function to check Node.js version
check_node_version() {
    if command_exists node; then
        NODE_VERSION=$(node -v | cut -d'v' -f2)
        if (( $(echo "$NODE_VERSION < 14.0.0" | bc -l) )); then
            echo -e "${RED}Error: Node.js 14.0.0 or higher is required. Found version $NODE_VERSION${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Error: Node.js is not installed${NC}"
        exit 1
    fi
}

# Function to setup Python virtual environment
setup_python_env() {
    echo -e "${GREEN}Setting up Python virtual environment...${NC}"
    
    # Check if venv exists
    if [ ! -d "backend/venv" ]; then
        python3 -m venv backend/venv
    fi
    
    # Activate virtual environment
    source backend/venv/bin/activate
    
    # Install/upgrade pip
    python -m pip install --upgrade pip
    
    # Install requirements
    echo -e "${GREEN}Installing Python dependencies...${NC}"
    pip install -r backend/requirements.txt
}

# Function to setup Node.js environment
setup_node_env() {
    echo -e "${GREEN}Setting up Node.js environment...${NC}"
    
    # Install dependencies
    cd frontend
    npm install
    cd ..
}

# Function to start the backend server
start_backend() {
    echo -e "${GREEN}Starting backend server...${NC}"
    cd backend
    source venv/bin/activate
    uvicorn main:app --reload --port 8000 &
    BACKEND_PID=$!
    cd ..
}

# Function to start the frontend server
start_frontend() {
    echo -e "${GREEN}Starting frontend server...${NC}"
    cd frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..
}

# Function to open the browser
open_browser() {
    echo -e "${GREEN}Opening browser...${NC}"
    sleep 5  # Wait for servers to start
    
    # Try different commands to open browser based on OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        open http://localhost:3000
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        xdg-open http://localhost:3000
    elif [[ "$OSTYPE" == "msys" ]]; then
        # Windows
        start http://localhost:3000
    else
        echo -e "${YELLOW}Please open http://localhost:3000 in your browser${NC}"
    fi
}

# Function to handle cleanup on exit
cleanup() {
    echo -e "\n${GREEN}Shutting down servers...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM

# Main execution
echo -e "${GREEN}Starting AI Personal Trainer...${NC}"

# Check prerequisites
check_python_version
check_node_version
check_env_vars

# Setup environments
setup_python_env
setup_node_env

# Start servers
start_backend
start_frontend

# Open browser
open_browser

echo -e "${GREEN}Servers are running!${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop the servers${NC}"

# Wait for user interrupt
wait 