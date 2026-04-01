#!/bin/bash
# Deploy the order node code to a Nanode.
# Usage: ./deploy/order-node-nanode/deploy-node.sh <nanode-ip>
#
# Run from the project root on your LOCAL machine.
# Prerequisite: run setup.sh on the Nanode first.
set -euo pipefail

NANODE_IP="${1:?Usage: ./deploy/order-node-nanode/deploy-node.sh <nanode-ip>}"
REMOTE_USER="deploy"
REMOTE_DIR="/opt/order-node"

echo "=== Deploying Order Node to ${NANODE_IP} ==="

# Sync order node code
echo "[1/3] Syncing order node code..."
rsync -avz \
    backend/order_node/ ${REMOTE_USER}@${NANODE_IP}:${REMOTE_DIR}/order_node/

# Sync the shared proxy module (OrderNodeProxy) and upstox_client
rsync -avz \
    backend/services/order_node_proxy.py ${REMOTE_USER}@${NANODE_IP}:${REMOTE_DIR}/services/
rsync -avz \
    backend/services/upstox_client.py ${REMOTE_USER}@${NANODE_IP}:${REMOTE_DIR}/services/
rsync -avz \
    backend/services/__init__.py ${REMOTE_USER}@${NANODE_IP}:${REMOTE_DIR}/services/

# Sync requirements (minimal — just what the order node needs)
cat > /tmp/order-node-requirements.txt << 'EOF'
fastapi>=0.115.0
uvicorn>=0.32.0
upstox-client>=2.12.0
httpx>=0.27.0
pydantic>=2.10.0
EOF
rsync -avz /tmp/order-node-requirements.txt ${REMOTE_USER}@${NANODE_IP}:${REMOTE_DIR}/requirements.txt

# Remote: install deps + restart
echo "[2/3] Installing deps..."
ssh ${REMOTE_USER}@${NANODE_IP} << 'ENDSSH'
set -euo pipefail
cd /opt/order-node

# Create services/__init__.py if missing
mkdir -p services
touch services/__init__.py

# Python venv + deps
if [ ! -d "venv" ]; then
    python3.12 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
ENDSSH

echo "[3/3] Restarting order node service..."
ssh root@${NANODE_IP} "systemctl restart order-node && systemctl status order-node --no-pager"

echo ""
echo "=== Deploy complete ==="
echo "Health check: curl http://${NANODE_IP}:8001/health"
