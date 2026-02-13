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

# --- Remote: install deps ---
echo "[4/5] Installing backend deps..."
ssh ${REMOTE_USER}@${SERVER_IP} << 'ENDSSH'
set -euo pipefail

cd /opt/niftystrategist/backend

# Python venv + deps
if [ ! -d "venv" ]; then
    python3.12 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt 2>/dev/null || pip install -q -r pyproject.toml 2>/dev/null || echo "Install deps manually if needed"
ENDSSH

# --- Restart service (as root, since deploy user sudo is restricted) ---
echo "[5/5] Restarting service..."
ssh root@${SERVER_IP} "systemctl restart niftystrategist && systemctl status niftystrategist --no-pager"

echo ""
echo "=== Deploy complete ==="
