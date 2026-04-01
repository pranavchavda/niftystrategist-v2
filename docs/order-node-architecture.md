# Per-User Order Node Architecture

## Why This Exists

SEBI mandated (effective April 1, 2026) that all broker API order placement must originate from a static IP registered to the individual customer. One IP = one customer (family up to 5 can share). This broke NiftyStrategist's multi-user model where all users' orders went through the main server's IP.

**Solution:** Each user gets a dedicated "order node" — a thin FastAPI proxy running on its own Linode Nanode ($5/mo) with its own static IP. The main NS instance routes order-mutating API calls through the user's node. Non-order APIs (quotes, holdings, positions, analysis) are unaffected and go direct.

## Architecture

```
Main NS Instance (172.105.40.112)
├── Full app: chat, AI agent, dashboard, analysis, monitor daemon
├── Order node for Pranav: http://localhost:8001
└── For other users: routes orders to their Nanode
     └── e.g., http://172.105.40.186:8001 (User 5)

Per-User Nanode ($5/mo)
├── Thin FastAPI (order_node/app.py) — ~150 lines
├── Endpoints: place, modify, cancel, cancel-all, exit-all, place-multi
├── Stateless: receives Upstox token per-request, never stores it
├── Firewalled: port 8001 only accepts from main NS IP
└── Auth: Bearer token + X-Node-Secret shared secret
```

## What Routes Through the Order Node

Only order-mutating Upstox API calls:
- Place order (equity + F&O)
- Modify order
- Cancel order
- Cancel all orders
- Exit all positions
- Place multi-leg order (spreads)

Everything else goes direct from the main instance — no IP restriction on:
- Quotes, LTP, OHLC, historical data
- Holdings, positions, funds, profile
- Option chain, greeks
- Market status
- Trade history, order book (read-only)

## How It Works

### Flow: Chat Agent → Order

```
User: "Buy 10 RELIANCE"
  → Orchestrator calls execute_bash("nf-order buy RELIANCE 10")
    → Subprocess gets NF_ORDER_NODE_URL from env
      → nf-order resolves instrument_token locally
        → POSTs to user's order node
          → Order node calls Upstox SDK from its own IP
            → Returns result to nf-order
              → Agent shows result to user
```

### Flow: Monitor Daemon → Order

```
Rule fires (price trigger)
  → ActionExecutor checks user's order_node_url
    → POSTs to user's order node via OrderNodeProxy (async)
      → Order node calls Upstox SDK
        → Returns result, logged in monitor_logs
```

### Key: The agent doesn't know about any of this. It still calls `nf-order` / `nf-options` as always. The routing is invisible.

## Current Deployment

| User | ID | Order Node URL | IP | Location |
|------|----|----------------|----|----------|
| Pranav Chavda | 1 | `http://localhost:8001` | 172.105.40.112 | Main instance |
| Ashok Chavda | 5 | `http://172.105.40.186:8001` | 172.105.40.186 | Nanode `ns-ordernode-user5` |

## Key Files

| File | Purpose |
|------|---------|
| `backend/order_node/app.py` | The order node FastAPI service |
| `backend/services/order_node_proxy.py` | Sync `OrderNodeClient` (CLI) + async `OrderNodeProxy` (daemon) |
| `backend/database/models.py` | `User.order_node_url` column |
| `backend/migrations/022_add_order_node_url.sql` | DB migration |
| `backend/cli-tools/nf-order` | Checks `NF_ORDER_NODE_URL`, proxies if set |
| `backend/cli-tools/nf-options` | Same for options buy/sell/spread |
| `backend/agents/orchestrator.py` | `OrchestratorDeps.order_node_url` + env injection |
| `backend/monitor/action_executor.py` | Routes place/cancel through node |
| `backend/monitor/daemon.py` | Loads `order_node_urls` from DB during poll |
| `deploy/niftystrategist-ordernode.service` | systemd unit for main instance (localhost) |
| `deploy/order-node-nanode/setup.sh` | Nanode provisioning script |
| `deploy/order-node-nanode/deploy-node.sh` | Deploy order node code to Nanode |

## Auth

- **Bearer token**: The user's decrypted Upstox access token, passed per-request in the `Authorization` header. The order node never stores tokens — the main instance handles all TOTP refresh and token management.
- **X-Node-Secret**: Shared secret between main instance and all nodes. Set in `.env` as `NF_ORDER_NODE_SECRET` on both sides.
- **Firewall**: Each Nanode's UFW restricts port 8001 to only accept connections from the main NS IP (172.105.40.112).

## Adding a New User's Order Node

### Prerequisites
- Linode API token (stored in Claude memory)
- User already exists in NiftyStrategist DB
- User has their own Upstox API app (key + secret in Settings)

### Step-by-step

```bash
# ── 1. Create the Nanode via Linode API ──────────────────────────
LINODE_TOKEN="<from-memory>"
USER_ID=<db-user-id>
USER_NAME="<short-name>"  # e.g., "user7"

NANODE_IP=$(curl -s -X POST \
  -H "Authorization: Bearer $LINODE_TOKEN" \
  -H "Content-Type: application/json" \
  https://api.linode.com/v4/linode/instances \
  -d "{
    \"label\": \"ns-ordernode-${USER_NAME}\",
    \"region\": \"ap-west\",
    \"type\": \"g6-nanode-1\",
    \"image\": \"linode/ubuntu24.04\",
    \"root_pass\": \"$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')\",
    \"authorized_keys\": [\"$(cat ~/.ssh/id_ed25519.pub)\"],
    \"booted\": true
  }" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['ipv4'][0])")

echo "Nanode IP: $NANODE_IP"
# Wait ~90 seconds for provisioning + boot

# ── 2. SSH setup ─────────────────────────────────────────────────
ssh-keyscan -H $NANODE_IP >> ~/.ssh/known_hosts

# ── 3. Server setup ─────────────────────────────────────────────
ssh root@$NANODE_IP << 'EOF'
  apt update && apt install -y python3.12 python3.12-venv ufw

  # Deploy user
  useradd -m -s /bin/bash deploy
  mkdir -p /home/deploy/.ssh
  cp /root/.ssh/authorized_keys /home/deploy/.ssh/
  chown -R deploy:deploy /home/deploy/.ssh
  chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys

  # Firewall: SSH + port 8001 from main NS only
  ufw allow OpenSSH
  ufw allow from 172.105.40.112 to any port 8001
  echo y | ufw enable

  # App directory
  mkdir -p /opt/order-node
  chown deploy:deploy /opt/order-node

  # Systemd unit
  cat > /etc/systemd/system/order-node.service << 'UNIT'
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
UNIT
  systemctl daemon-reload && systemctl enable order-node
EOF

# ── 4. Create .env on Nanode ─────────────────────────────────────
# Use the same NF_ORDER_NODE_SECRET as the main instance
ssh root@$NANODE_IP "echo 'NF_ORDER_NODE_SECRET=<secret-from-main-env>' > /opt/order-node/.env && chown deploy:deploy /opt/order-node/.env"

# ── 5. Deploy order node code ───────────────────────────────────
cd /path/to/niftystrategist-v2
ssh deploy@$NANODE_IP "mkdir -p /opt/order-node/order_node /opt/order-node/services"
rsync -avz backend/order_node/ deploy@$NANODE_IP:/opt/order-node/order_node/
rsync -avz backend/services/order_node_proxy.py deploy@$NANODE_IP:/opt/order-node/services/
rsync -avz backend/services/upstox_client.py deploy@$NANODE_IP:/opt/order-node/services/
ssh deploy@$NANODE_IP "touch /opt/order-node/services/__init__.py"

# ── 6. Install Python deps ──────────────────────────────────────
ssh deploy@$NANODE_IP << 'EOF'
  cd /opt/order-node
  python3.12 -m venv venv
  source venv/bin/activate
  pip install -q fastapi uvicorn httpx pydantic upstox-python-sdk
EOF

# ── 7. Start the service ────────────────────────────────────────
ssh root@$NANODE_IP "systemctl start order-node"

# ── 8. Health check from main instance ───────────────────────────
ssh deploy@172.105.40.112 "curl -sf http://${NANODE_IP}:8001/health"
# Should return: {"ok": true}

# ── 9. Set order_node_url in database ────────────────────────────
ssh deploy@172.105.40.112 "cd /opt/niftystrategist/backend && source venv/bin/activate && python3 -c \"
from dotenv import load_dotenv; load_dotenv('.env')
import asyncio
from database.session import get_db_context
from sqlalchemy import text
async def main():
    async with get_db_context() as s:
        await s.execute(text(\\\"UPDATE users SET order_node_url = 'http://${NANODE_IP}:8001' WHERE id = ${USER_ID}\\\"))
        await s.commit()
        print('Done')
asyncio.run(main())
\""

# ── 10. Restart main services to pick up new URL ────────────────
ssh root@172.105.40.112 "systemctl restart niftystrategist && systemctl restart niftystrategist-monitor"

# ── 11. User action: register IP in Upstox ──────────────────────
echo "Tell the user to register ${NANODE_IP} as their primary static IP"
echo "at https://account.upstox.com/developer/apps"
```

### Updating order node code (after main repo changes)

```bash
# Re-deploy to all Nanodes after code changes to order_node/
NANODES="172.105.40.186"  # space-separated list

for IP in $NANODES; do
  rsync -avz backend/order_node/ deploy@$IP:/opt/order-node/order_node/
  rsync -avz backend/services/order_node_proxy.py deploy@$IP:/opt/order-node/services/
  ssh root@$IP "systemctl restart order-node"
  echo "Updated $IP"
done
```

### Troubleshooting

```bash
# Check order node logs on a Nanode
ssh root@<nanode-ip> "journalctl -u order-node -f"

# Check order node logs on main instance
ssh root@172.105.40.112 "journalctl -u niftystrategist-ordernode -f"

# Test an order node directly
curl -X POST http://<nanode-ip>:8001/orders/place \
  -H "Authorization: Bearer <upstox-token>" \
  -H "X-Node-Secret: <secret>" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"TEST","instrument_token":"NSE_EQ|INE002A01018","transaction_type":"BUY","quantity":1,"order_type":"MARKET"}'

# Check which users have order nodes configured
psql $DATABASE_URL -c "SELECT id, name, order_node_url FROM users WHERE order_node_url IS NOT NULL"

# Check firewall on Nanode
ssh root@<nanode-ip> "ufw status"
```

## Cost

- $5/month per user (Linode Nanode 1GB)
- Main instance order node: $0 (runs on existing server)
- Total for 2 users: $5/month

## Future Considerations

- **Analytics token migration**: Upstox now offers a 1-year read-only analytics token (no IP restriction). Could use it for the monitor daemon's WebSocket data streams, eliminating token expiry issues for market data. See memory for details.
- **Automation script**: If user count grows, wrap the add-user steps into `scripts/add-user-node.sh` using the Linode API.
- **CI/CD for Nanodes**: Currently manual rsync. Could add Nanode IPs to the GitHub Actions deploy workflow for automatic updates on push.
