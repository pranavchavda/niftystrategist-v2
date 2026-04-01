#!/bin/bash
# Minimal setup for a per-user Order Node Nanode ($5/mo).
# Run: ssh root@<nanode-ip> < deploy/order-node-nanode/setup.sh
#
# Prerequisites: Fresh Ubuntu 24.04 Nanode on Linode.
# After running this, deploy the order node code with deploy-node.sh.
set -euo pipefail

MAIN_NS_IP="172.105.40.112"

echo "=== Order Node Nanode Setup ==="

# System updates
apt update && apt upgrade -y

# Python 3.12
apt install -y python3.12 python3.12-venv ufw

# Create deploy user (matches main instance convention)
if ! id deploy &>/dev/null; then
    useradd -m -s /bin/bash deploy
    echo "Created deploy user"
fi

# Firewall: SSH + order node port (8001) from main NS IP only
ufw allow OpenSSH
ufw allow from ${MAIN_NS_IP} to any port 8001
ufw --force enable
echo "UFW configured: SSH open, port 8001 restricted to ${MAIN_NS_IP}"

# App directory
mkdir -p /opt/order-node
chown deploy:deploy /opt/order-node

# Systemd unit
cat > /etc/systemd/system/order-node.service << 'EOF'
[Unit]
Description=NiftyStrategist Order Node
After=network.target

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/opt/order-node
EnvironmentFile=/opt/order-node/.env
ExecStart=/opt/order-node/venv/bin/uvicorn order_node.app:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable order-node

echo ""
echo "=== Setup complete ==="
echo "Next: run deploy/order-node-nanode/deploy-node.sh <nanode-ip>"
echo "Then: create /opt/order-node/.env with NF_ORDER_NODE_SECRET=<secret>"
