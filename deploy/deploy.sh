#!/bin/bash
# NiftyStrategist - Deploy script
# Run from the project root on your LOCAL machine
# Usage: ./deploy/deploy.sh <server-ip>
set -euo pipefail

SERVER_IP="${1:?Usage: ./deploy/deploy.sh <server-ip>}"
REMOTE_USER="deploy"
REMOTE_DIR="/opt/niftystrategist"

echo "=== Deploying NiftyStrategist to $SERVER_IP ==="

# --- Build frontend locally ---
echo "[1/4] Building frontend..."
cd frontend-v2
pnpm install --frozen-lockfile
pnpm run build
cd ..

# --- Sync backend ---
echo "[2/4] Syncing backend..."
rsync -avz --delete \
    --exclude 'venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude '.pytest_cache/' \
    backend/ ${REMOTE_USER}@${SERVER_IP}:${REMOTE_DIR}/backend/

# --- Sync frontend build ---
echo "[3/4] Syncing frontend build..."
rsync -avz --delete \
    frontend-v2/build/ ${REMOTE_USER}@${SERVER_IP}:${REMOTE_DIR}/frontend/build/

# Also sync package.json and node_modules needed for react-router-serve
rsync -avz \
    frontend-v2/package.json ${REMOTE_USER}@${SERVER_IP}:${REMOTE_DIR}/frontend/

# --- Remote: install deps and restart ---
echo "[4/4] Installing deps and restarting services..."
ssh ${REMOTE_USER}@${SERVER_IP} << 'ENDSSH'
set -euo pipefail

cd /opt/niftystrategist/backend

# Python venv + deps
if [ ! -d "venv" ]; then
    python3.12 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt 2>/dev/null || pip install -q -r pyproject.toml 2>/dev/null || echo "Install deps manually if needed"

# Frontend deps (for react-router-serve)
cd /opt/niftystrategist/frontend
pnpm install --prod 2>/dev/null || npm install --production 2>/dev/null || true

echo "Deploy sync complete. Restart services with:"
echo "  sudo systemctl restart niftystrategist-backend niftystrategist-frontend"
ENDSSH

echo ""
echo "=== Deploy complete ==="
echo "SSH in and restart: sudo systemctl restart niftystrategist-backend niftystrategist-frontend"
