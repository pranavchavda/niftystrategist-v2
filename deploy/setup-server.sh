#!/bin/bash
# NiftyStrategist - One-time server setup for Ubuntu 24.04 LTS
# Run as root on a fresh Linode Nanode
set -euo pipefail

echo "=== NiftyStrategist Server Setup ==="

# --- System updates ---
apt update && apt upgrade -y

# --- Create deploy user ---
if ! id "deploy" &>/dev/null; then
    useradd -m -s /bin/bash deploy
    echo "Created 'deploy' user"
else
    echo "'deploy' user already exists"
fi

# --- Install system packages ---
apt install -y \
    python3.12 python3.12-venv python3-pip \
    nodejs npm \
    caddy \
    git \
    ufw

# --- Install Node 22 via NodeSource ---
# Ubuntu 24.04 ships Node 18; we need 22
if node --version 2>/dev/null | grep -q "v22"; then
    echo "Node 22 already installed"
else
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt install -y nodejs
    echo "Node $(node --version) installed"
fi

# --- Install pnpm ---
npm install -g pnpm

# --- Create app directory ---
mkdir -p /opt/niftystrategist/{backend,frontend}
chown -R deploy:deploy /opt/niftystrategist

# --- Firewall ---
ufw allow OpenSSH
ufw allow 80
ufw allow 443
echo "y" | ufw enable
echo "Firewall configured (SSH, HTTP, HTTPS)"

# --- Caddy ---
# Caddyfile will be deployed separately
echo "Caddy installed. Place Caddyfile at /etc/caddy/Caddyfile"

# --- Systemd services ---
echo "Copy service files to /etc/systemd/system/ then run:"
echo "  systemctl daemon-reload"
echo "  systemctl enable niftystrategist-backend niftystrategist-frontend"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Point niftystrategist.com DNS A record to this server's IP"
echo "  2. Copy the app code to /opt/niftystrategist/"
echo "  3. Set up backend venv and .env"
echo "  4. Build frontend"
echo "  5. Copy Caddyfile to /etc/caddy/Caddyfile and restart caddy"
echo "  6. Copy systemd services, enable, and start"
