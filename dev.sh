#!/bin/bash

# Nifty Strategist v2 - Development Server Script
# AI Trading Assistant for Indian Stock Markets

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-5173}
LOG_DIR="logs"

# Print colored output
print_color() {
    echo -e "${2}${1}${NC}"
}

print_header() {
    echo ""
    print_color "================================================" "$BLUE"
    print_color "$1" "$GREEN"
    print_color "================================================" "$BLUE"
    echo ""
}

# Function to check if port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_color "Port $1 is already in use!" "$YELLOW"
        return 1
    fi
    return 0
}

# Function to kill process on port
kill_port() {
    local port=$1
    local pid=$(lsof -t -i:$port 2>/dev/null)
    if [ ! -z "$pid" ]; then
        print_color "Port $port is in use by process $pid. Killing it..." "$YELLOW"
        kill -9 $pid 2>/dev/null || true
        sleep 1
        print_color "Port $port cleared" "$GREEN"
    fi
}

# Cleanup function
cleanup() {
    print_header "Shutting down Nifty Strategist services..."

    # Kill all child processes
    jobs -p | xargs -r kill 2>/dev/null || true

    # Deactivate virtual environment if active
    if [ "$VIRTUAL_ENV" != "" ]; then
        deactivate 2>/dev/null || true
    fi

    print_color "All services stopped" "$GREEN"
    exit
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Parse command line arguments
MODE="both"
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --backend-only)
            MODE="backend"
            shift
            ;;
        --frontend-only)
            MODE="frontend"
            shift
            ;;
        --cli)
            MODE="cli"
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Nifty Strategist v2 Development Server"
            echo ""
            echo "Options:"
            echo "  --backend-only    Start only the backend server (FastAPI)"
            echo "  --frontend-only   Start only the frontend server (React)"
            echo "  --cli            Start CLI interface instead of servers"
            echo "  --verbose        Show detailed output"
            echo "  --help           Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  BACKEND_PORT     Backend port (default: 8000)"
            echo "  FRONTEND_PORT    Frontend port (default: 5173)"
            exit 0
            ;;
        *)
            print_color "Unknown option: $1" "$RED"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

print_header "Nifty Strategist v2 - Development Server"
print_color "AI Trading Assistant for Indian Stock Markets" "$CYAN"
echo ""

# Check if we're in the project root
if [ ! -f "backend/main.py" ] || [ ! -f "frontend-v2/package.json" ]; then
    print_color "Error: Must run from project root directory" "$RED"
    print_color "   Current directory: $(pwd)" "$YELLOW"
    print_color "   Expected: /home/pranav/niftystrategist-v2/" "$YELLOW"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
REQUIRED_PYTHON="3.11"

if [ "$(printf '%s\n' "$REQUIRED_PYTHON" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_PYTHON" ]; then
    print_color "Python $REQUIRED_PYTHON or higher is required (found $PYTHON_VERSION)" "$YELLOW"
fi

# Function to start backend
start_backend() {
    print_header "Starting Backend Server (FastAPI)"

    # Kill any existing process on the port
    kill_port $BACKEND_PORT

    cd backend

    # Set up virtual environment
    if [ ! -d "venv" ]; then
        print_color "Creating Python virtual environment..." "$YELLOW"
        python3 -m venv venv
    fi

    # Activate virtual environment
    print_color "Activating virtual environment..." "$BLUE"
    source venv/bin/activate

    # Check if key dependencies are installed (use venv python explicitly)
    if ! venv/bin/python -c "import fastapi" 2>/dev/null; then
        print_color "FastAPI not found in venv. Installing dependencies..." "$YELLOW"
        if [ -f "requirements.txt" ]; then
            venv/bin/pip install -r requirements.txt
        else
            venv/bin/pip install fastapi uvicorn pydantic-ai sqlalchemy asyncpg
        fi
    fi

    # Load environment variables
    if [ -f ".env" ]; then
        print_color "Loading environment variables from .env" "$BLUE"
        export $(grep -v '^#' .env | xargs)
    fi

    # WSL-specific note
    if grep -qi microsoft /proc/version 2>/dev/null; then
        print_color "WSL detected - database connection may have higher latency" "$YELLOW"
    fi

    # Start backend server
    if [ "$VERBOSE" = true ]; then
        print_color "Starting backend in verbose mode..." "$YELLOW"
        uvicorn main:app --reload --reload-exclude 'venv/*' --host 0.0.0.0 --port $BACKEND_PORT --log-level debug 2>&1 | tee "../$LOG_DIR/backend.log" &
    else
        uvicorn main:app --reload --reload-exclude 'venv/*' --host 0.0.0.0 --port $BACKEND_PORT > "../$LOG_DIR/backend.log" 2>&1 &
    fi

    BACKEND_PID=$!

    # Wait for backend to be ready
    print_color "Waiting for backend to be ready..." "$YELLOW"
    for i in {1..30}; do
        if curl -s "http://localhost:$BACKEND_PORT/health" > /dev/null 2>&1; then
            print_color "Backend is ready at http://localhost:$BACKEND_PORT" "$GREEN"
            print_color "   API Docs: http://localhost:$BACKEND_PORT/docs" "$BLUE"
            break
        fi
        if [ $i -eq 30 ]; then
            print_color "Backend health check timed out after 30 seconds" "$YELLOW"
            print_color "   Check logs at $LOG_DIR/backend.log for details" "$BLUE"
        fi
        sleep 1
    done

    cd ..
}

# Function to start frontend
start_frontend() {
    print_header "Starting Frontend Server (React Router)"

    # Kill any existing process on the port
    kill_port $FRONTEND_PORT

    cd frontend-v2

    # Check Node.js version and switch to v22+ if needed
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node -v | grep -oE '[0-9]+' | head -n1)
        print_color "Current Node.js version: v$NODE_VERSION" "$BLUE"

        if [ "$NODE_VERSION" -lt 22 ]; then
            print_color "Node.js version $NODE_VERSION is below 22" "$YELLOW"

            # Check if nvm is available
            if [ -s "$HOME/.nvm/nvm.sh" ]; then
                print_color "Loading nvm and switching to Node.js v22..." "$YELLOW"
                export NVM_DIR="$HOME/.nvm"
                [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

                # Install Node.js v22 if not already installed
                if ! nvm ls 22 &> /dev/null; then
                    print_color "Installing Node.js v22..." "$YELLOW"
                    nvm install 22
                fi

                # Use Node.js v22
                nvm use 22
                NEW_VERSION=$(node -v | grep -oE '[0-9]+' | head -n1)
                print_color "Switched to Node.js v$NEW_VERSION" "$GREEN"
            else
                print_color "nvm not found. Please install nvm or upgrade Node.js to v22+" "$RED"
                print_color "   Visit: https://github.com/nvm-sh/nvm#installing-and-updating" "$BLUE"
                exit 1
            fi
        else
            print_color "Node.js version is sufficient (v$NODE_VERSION >= 22)" "$GREEN"
        fi
    else
        print_color "Node.js not found. Please install Node.js v22 or higher." "$RED"
        exit 1
    fi

    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        print_color "Installing frontend dependencies with npm..." "$YELLOW"
        npm install
    fi

    # Start frontend server
    if [ "$VERBOSE" = true ]; then
        print_color "Starting frontend in verbose mode..." "$YELLOW"
        VITE_API_URL="http://localhost:$BACKEND_PORT" npm run dev 2>&1 | tee "../$LOG_DIR/frontend.log" &
    else
        VITE_API_URL="http://localhost:$BACKEND_PORT" npm run dev > "../$LOG_DIR/frontend.log" 2>&1 &
    fi

    FRONTEND_PID=$!

    # Wait for frontend to be ready
    print_color "Waiting for frontend to be ready..." "$YELLOW"
    sleep 3
    print_color "Frontend is ready at http://localhost:$FRONTEND_PORT" "$GREEN"

    cd ..
}

# Function to start CLI
start_cli() {
    print_header "Starting CLI Interface"

    cd backend

    # Set up virtual environment
    if [ ! -d "venv" ]; then
        print_color "Creating Python virtual environment..." "$YELLOW"
        python3 -m venv venv
    fi

    # Activate virtual environment
    print_color "Activating virtual environment..." "$BLUE"
    source venv/bin/activate

    # Check if key dependencies are installed (use venv python explicitly)
    if ! venv/bin/python -c "import pydantic_ai" 2>/dev/null; then
        print_color "pydantic-ai not found in venv. Installing dependencies..." "$YELLOW"
        if [ -f "requirements.txt" ]; then
            venv/bin/pip install -r requirements.txt
        else
            venv/bin/pip install pydantic-ai
        fi
    fi

    # Load environment variables
    if [ -f ".env" ]; then
        export $(grep -v '^#' .env | xargs)
    fi

    print_color "Starting interactive CLI..." "$GREEN"
    venv/bin/python cli.py
}

# Main execution
case $MODE in
    backend)
        start_backend
        print_header "Backend server is running!"
        print_color "Press Ctrl+C to stop" "$YELLOW"
        wait $BACKEND_PID
        ;;
    frontend)
        start_frontend
        print_header "Frontend server is running!"
        print_color "Press Ctrl+C to stop" "$YELLOW"
        wait $FRONTEND_PID
        ;;
    cli)
        start_cli
        ;;
    both)
        start_backend
        start_frontend

        print_header "All services started successfully!"
        echo ""
        print_color "  Frontend: http://localhost:$FRONTEND_PORT" "$CYAN"
        print_color "  Backend:  http://localhost:$BACKEND_PORT" "$CYAN"
        print_color "  API Docs: http://localhost:$BACKEND_PORT/docs" "$CYAN"
        echo ""

        if [ "$VERBOSE" = false ]; then
            print_color "Logs are being written to:" "$BLUE"
            echo "   - Backend:  $LOG_DIR/backend.log"
            echo "   - Frontend: $LOG_DIR/frontend.log"
            echo ""
        fi

        print_color "Press Ctrl+C to stop all services" "$YELLOW"

        # Wait for both processes
        wait $BACKEND_PID $FRONTEND_PID
        ;;
esac
