#!/bin/bash

# Nifty Strategist v2 - Development Server Script
# AI Trading Assistant for Indian Stock Markets

set -e  # Exit on error

# Always operate relative to this script's location, regardless of where it's
# invoked from. This makes the project portable across machines (no hardcoded
# absolute paths).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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
# Minimum Python the backend needs (upstox-totp requires >=3.12). uv will fetch
# a managed interpreter of this version if the system doesn't have one.
PYTHON_PIN=${PYTHON_PIN:-3.12}

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
    print_color "Error: backend/main.py or frontend-v2/package.json not found" "$RED"
    print_color "   Script directory: $SCRIPT_DIR" "$YELLOW"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Check Python version
# Note: this only inspects the system python3 for an informational warning.
# The actual venv is created by uv pinned to $PYTHON_PIN regardless, so a stale
# or missing system python3 won't block startup.
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
if [ -n "$PYTHON_VERSION" ] && [ "$(printf '%s\n' "$PYTHON_PIN" "$PYTHON_VERSION" | sort -V | head -n1)" != "$PYTHON_PIN" ]; then
    print_color "System python3 is $PYTHON_VERSION; backend uses uv-managed Python $PYTHON_PIN" "$BLUE"
fi

# Ensure `uv` is available, installing it if missing.
ensure_uv() {
    if command -v uv &> /dev/null; then
        return 0
    fi

    # uv may be installed but not on PATH (common install locations)
    for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [ -x "$candidate" ]; then
            export PATH="$(dirname "$candidate"):$PATH"
            return 0
        fi
    done

    print_color "uv not found. Installing uv..." "$YELLOW"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # The installer drops uv into ~/.local/bin (newer) or ~/.cargo/bin (older)
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

    if ! command -v uv &> /dev/null; then
        print_color "Failed to install uv automatically." "$RED"
        print_color "   Install it manually: https://docs.astral.sh/uv/getting-started/installation/" "$BLUE"
        exit 1
    fi
    print_color "Installed $(uv --version)" "$GREEN"
}

# Create/repair the backend venv (relative to the current dir) and install deps.
# $1 = python module to probe for, $2 = friendly name, $3 = fallback packages.
setup_python_env() {
    local probe_module="$1"
    local friendly_name="$2"
    local fallback_packages="$3"

    ensure_uv

    # Decide whether to (re)create the venv. Recreate if it's:
    #   - missing
    #   - broken/stale (e.g. synced from another machine via Syncthing, so its
    #     interpreter symlinks no longer resolve)
    #   - built on a Python older than $PYTHON_PIN (deps like upstox-totp need >=3.12)
    local recreate_reason=""
    if [ ! -x "venv/bin/python" ] || ! venv/bin/python -c "" 2>/dev/null; then
        [ -d "venv" ] && recreate_reason="broken or from another machine"
    elif ! venv/bin/python -c "import sys; req=tuple(int(x) for x in '${PYTHON_PIN}'.split('.')); sys.exit(0 if sys.version_info[:len(req)] >= req else 1)" 2>/dev/null; then
        recreate_reason="Python older than $PYTHON_PIN"
    else
        # venv is present and satisfies the version pin — nothing to do here.
        recreate_reason="keep"
    fi

    if [ "$recreate_reason" != "keep" ]; then
        if [ -d "venv" ]; then
            print_color "Existing venv unusable ($recreate_reason). Recreating with uv (Python $PYTHON_PIN)..." "$YELLOW"
            rm -rf venv
        else
            print_color "Creating Python virtual environment with uv (Python $PYTHON_PIN)..." "$YELLOW"
        fi
        uv venv --python "$PYTHON_PIN" venv
    fi

    # Activate virtual environment
    print_color "Activating virtual environment..." "$BLUE"
    source venv/bin/activate

    # Install dependencies if the probe import fails
    if ! venv/bin/python -c "import ${probe_module}" 2>/dev/null; then
        print_color "${friendly_name} not found in venv. Installing dependencies with uv..." "$YELLOW"
        if [ -f "requirements.txt" ]; then
            uv pip install -r requirements.txt
        else
            uv pip install ${fallback_packages}
        fi
    fi
}

# Ensure `pnpm` is available, bootstrapping it if missing. Call after any nvm
# switch so corepack/npm resolve to the active Node.
ensure_pnpm() {
    if command -v pnpm &> /dev/null; then
        return 0
    fi

    # Prefer corepack (ships with modern Node); fall back to a global npm install
    if command -v corepack &> /dev/null; then
        print_color "Enabling pnpm via corepack..." "$YELLOW"
        corepack enable pnpm 2>/dev/null || corepack prepare pnpm@latest --activate 2>/dev/null || true
    fi
    if ! command -v pnpm &> /dev/null; then
        print_color "Installing pnpm globally via npm..." "$YELLOW"
        npm install -g pnpm
    fi

    if ! command -v pnpm &> /dev/null; then
        print_color "Failed to install pnpm automatically." "$RED"
        print_color "   Install it manually: https://pnpm.io/installation" "$BLUE"
        exit 1
    fi
    print_color "Using pnpm $(pnpm --version)" "$GREEN"
}

# Function to start backend
start_backend() {
    print_header "Starting Backend Server (FastAPI)"

    # Kill any existing process on the port
    kill_port $BACKEND_PORT

    cd backend

    # Set up / repair virtual environment and install deps (via uv)
    setup_python_env fastapi "FastAPI" "fastapi uvicorn pydantic-ai sqlalchemy asyncpg"

    # Load environment variables
    if [ -f ".env" ]; then
        print_color "Loading environment variables from .env" "$BLUE"
        export $(grep -v '^#' .env | xargs)
    fi

    # Default: skip Telegram bot polling in dev to avoid getUpdates conflicts
    # with prod (which polls the same per-user tokens). Override via .env if you
    # want telegram in dev (set NF_DISABLE_TELEGRAM_BOT=0 and use a separate
    # dev bot token).
    if [ -z "$NF_DISABLE_TELEGRAM_BOT" ]; then
        export NF_DISABLE_TELEGRAM_BOT=1
        print_color "Telegram bot polling disabled in dev (set NF_DISABLE_TELEGRAM_BOT=0 in .env to enable)" "$YELLOW"
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

    # Check Node.js version and switch to v24+ if needed
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node -v | grep -oE '[0-9]+' | head -n1)
        print_color "Current Node.js version: v$NODE_VERSION" "$BLUE"

        if [ "$NODE_VERSION" -lt 24 ]; then
            print_color "Node.js version $NODE_VERSION is below 22" "$YELLOW"

            # Check if nvm is available
            if [ -s "$HOME/.nvm/nvm.sh" ]; then
                print_color "Loading nvm and switching to Node.js v24..." "$YELLOW"
                export NVM_DIR="$HOME/.nvm"
                [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

                # Install Node.js v24 if not already installed
                if ! nvm ls 24 &> /dev/null; then
                    print_color "Installing Node.js v24..." "$YELLOW"
                    nvm install 24
                fi

                # Use Node.js v24
                nvm use 24
                NEW_VERSION=$(node -v | grep -oE '[0-9]+' | head -n1)
                print_color "Switched to Node.js v$NEW_VERSION" "$GREEN"
            else
                print_color "nvm not found. Please install nvm or upgrade Node.js to v24+" "$RED"
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

    # Install / repair frontend dependencies (via pnpm — project standard).
    # node_modules holds platform-specific native binaries (rollup, esbuild, …).
    # If it was installed on another OS/arch (e.g. synced from the Linux dev box
    # via Syncthing) those binaries won't load here, so we stamp a platform
    # marker on install and reinstall whenever it doesn't match this machine.
    ensure_pnpm
    PLATFORM_TAG="$(uname -sm)"
    PLATFORM_MARKER="node_modules/.dev-platform"
    if [ ! -d "node_modules" ]; then
        print_color "Installing frontend dependencies with pnpm..." "$YELLOW"
        pnpm install
        echo "$PLATFORM_TAG" > "$PLATFORM_MARKER"
    elif [ "$(cat "$PLATFORM_MARKER" 2>/dev/null)" != "$PLATFORM_TAG" ]; then
        print_color "node_modules was built for a different platform ($(cat "$PLATFORM_MARKER" 2>/dev/null || echo unknown)). Reinstalling with pnpm for $PLATFORM_TAG..." "$YELLOW"
        rm -rf node_modules
        pnpm install
        echo "$PLATFORM_TAG" > "$PLATFORM_MARKER"
    fi

    # Start frontend server
    if [ "$VERBOSE" = true ]; then
        print_color "Starting frontend in verbose mode..." "$YELLOW"
        VITE_API_URL="http://localhost:$BACKEND_PORT" pnpm run dev 2>&1 | tee "../$LOG_DIR/frontend.log" &
    else
        VITE_API_URL="http://localhost:$BACKEND_PORT" pnpm run dev > "../$LOG_DIR/frontend.log" 2>&1 &
    fi

    FRONTEND_PID=$!

    # Wait for frontend to actually respond (not just a fixed sleep — a crashed
    # dev server would otherwise be reported as "ready").
    print_color "Waiting for frontend to be ready..." "$YELLOW"
    for i in {1..30}; do
        if curl -s "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
            print_color "Frontend is ready at http://localhost:$FRONTEND_PORT" "$GREEN"
            break
        fi
        if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
            print_color "Frontend process exited during startup. Check $LOG_DIR/frontend.log" "$RED"
            break
        fi
        if [ $i -eq 30 ]; then
            print_color "Frontend not responding after 30s. Check $LOG_DIR/frontend.log" "$YELLOW"
        fi
        sleep 1
    done

    cd ..
}

# Function to start CLI
start_cli() {
    print_header "Starting CLI Interface"

    cd backend

    # Set up / repair virtual environment and install deps (via uv)
    setup_python_env pydantic_ai "pydantic-ai" "pydantic-ai"

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
