# Per-User Order Node Architecture

## Why This Exists

SEBI mandated (effective April 1, 2026) that all broker API order placement must originate from a static IP registered to the individual customer. One IP = one customer (family up to 5 can share). This broke NiftyStrategist's multi-user model where all users' orders went through the main server's IP.

**Solution:** Each user gets a dedicated "order node" — a thin FastAPI proxy running on its own Linode Nanode ($5/mo) with its own static IP. The main NS instance routes order-mutating API calls through the user's node. Non-order APIs (quotes, holdings, positions, analysis) are unaffected and go direct.

---

## ⚠️ UPDATE 2026-06-05 — Static IP now enforced on per-user READS too

Upstox extended `UDAPI1154` static-IP enforcement beyond orders to **all per-user account-data APIs**: holdings/portfolio, positions, funds, trades, profile, P&L metadata, MF holdings — and even `GET /v2/user/ip` itself. A request from any origin other than the user's registered static IP now returns **403 UDAPI1154**. Only **public/exchange-wide market data** (quotes, OHLC, option chain, greeks, market status — served by the shared **analytics token**, `UPSTOX_ANALYTICS_TOKEN`) remains IP-free.

This breaks the "thin order-only node" model: a per-user node that only proxies orders is no longer enough — the user's *reads* now 403 too because they still run from the main instance.

### Current solution: Upstox family accounts + shared main-box IP

Upstox lets **up to 5 accounts in one family share a single registered static IP**. So instead of one Nanode per user, we add each user to **Pranav's Upstox family** and register the **main box IP** for them — all their traffic (reads *and* orders) then originates from the main box and matches.

**Register the main box for a family member** — `PUT https://api.upstox.com/v2/user/ip`:
- Auth: the **user's** Upstox access token. Body: `{"primary_ip": "172.105.40.112", "secondary_ip": "2400:8904::2000:e0ff:fee6:fe6c"}`.
- **Register BOTH the v4 and the v6** of the main box — outbound to Upstox **defaults to IPv6** (`2400:8904::2000:e0ff:fee6:fe6c`), so a v4-only registration still 403s. Mirror exactly what user 1 (Pranav) has.
- Constraints: changeable **once per calendar week**; a successful change **invalidates the user's access token** (`access_tokens_invalidated: true`).
- **The PUT endpoint is itself IP-enforced** → it must be issued **from the user's *currently*-registered IP** (their existing Nanode). Chicken-and-egg: you can't move the IP from the new box. Fetch the user's current token on the main box, then `ssh` to the Nanode and `curl` the PUT from there.
- Helper: `backend/scripts/probe_static_ip.py {get|set} <user_id> [primary] [secondary]` (reads use `get_user_upstox_token`; run from `backend/`).

**Post-change steps:**
1. Re-auth: `get_user_upstox_token(uid, force_refresh=True)` (clear `users.upstox_totp_last_failed_at` first if a transient failure left a 30-min cooldown — the failure can be spurious right at cutover).
2. Repoint orders to the main box: `UPDATE users SET order_node_url='http://localhost:8001' WHERE id=<uid>` (same as Pranav). The user's Nanode is now redundant.
3. Verify a real read (portfolio/profile) succeeds from the main box, and `journalctl` shows 0 new `UDAPI1154`.

**Migrated 2026-06-05:** User 5 (Ashok) moved to the main box IP via this procedure; reads verified; `order_node_url` → `localhost:8001`; **Nanode `ns-ordernode-user5` (Linode 95335107) decommissioned.**

> Note `UDAPI100072` "Funds service accessible 5:30 AM–12:00 AM IST" (HTTP 423) is a nightly maintenance window, **not** an IP error.

### Future direction — beyond the family limit / non-family users (TODO at wider test/demo)

The family-share trick only covers up to **5 accounts** in one family, and only people you can actually add as Upstox family members. For real multi-user (strangers, or the 6th+ user), each user still needs **their own static IP** — but now their node must **tunnel ALL ip-restricted traffic (reads + orders), not just orders**. The current `order_node/app.py` only proxies order writes, so the plan is to turn the per-user node into a **full Upstox account-traffic tunnel** for that user:
- Simplest: a transport-level **forward proxy** on the node (CONNECT to `api.upstox.com:443` only, auth + firewalled to main NS). The main instance sets that proxy on the user's `UpstoxClient` (SDK `Configuration.proxy` + httpx `proxies=`) for all per-user account calls — no per-endpoint code. Public market data keeps using the analytics token directly.
- Alternative: explicit read endpoints on the node mirroring the write ones (more code, more brittle given `get_portfolio`'s post-processing).

**Local dev:** per-user account reads now 403 locally (dev origin ≠ registered IP). Plan: **tunnel local dev's Upstox traffic out through the main Linode box** (the registered IP) — e.g. SSH/SOCKS proxy through `172.105.40.112`. Public market data (analytics token) still works locally without a tunnel.

---

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

**⚠️ As of 2026-06-05 this list is out of date — see the UPDATE section above.** Per-user account reads (holdings, positions, funds, profile, trades, order book) are now IP-enforced too. Only public/exchange-wide market data is still unrestricted (and we serve it via the analytics token):
- Quotes, LTP, OHLC, historical data
- Option chain, greeks
- Market status

Per-user reads now require the registered IP (handled today by family-IP sharing on the main box, not the order node):
- ~~Holdings, positions, funds, profile~~ → 403 UDAPI1154 unless from registered IP
- ~~Trade history, order book (read-only)~~ → 403 UDAPI1154 unless from registered IP

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

| User | ID | Order Node URL | Registered Upstox IP | Location |
|------|----|----------------|----|----------|
| Pranav Chavda | 1 | `http://localhost:8001` | 172.105.40.112 + v6 `2400:8904::2000:e0ff:fee6:fe6c` | Main instance |
| Ashok Chavda | 5 | `http://localhost:8001` | same as Pranav (Upstox **family member**, shared main-box IP) | Main instance |

> As of 2026-06-05, both active users run entirely from the main box (orders via `localhost:8001`, reads via the shared family IP). No Nanodes are currently deployed — `ns-ordernode-user5` was decommissioned. The per-Nanode procedure below is retained for when we exceed the 5-member family limit or onboard non-family users (see the future-direction note in the UPDATE section — those nodes must tunnel reads **and** orders).

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

- **Current (2026-06-05): $0 in Nanodes.** Both users run on the main box via Upstox family-IP sharing; `ns-ordernode-user5` decommissioned.
- $5/month per user only once we exceed the 5-member family limit or onboard non-family users (each then needs their own Nanode — as a full reads+orders tunnel, see UPDATE section).
- Main instance order node: $0 (runs on existing server).

## Future Considerations

- **Analytics token migration**: Upstox now offers a 1-year read-only analytics token (no IP restriction). Could use it for the monitor daemon's WebSocket data streams, eliminating token expiry issues for market data. See memory for details.
- **Automation script**: If user count grows, wrap the add-user steps into `scripts/add-user-node.sh` using the Linode API.
- **CI/CD for Nanodes**: Currently manual rsync. Could add Nanode IPs to the GitHub Actions deploy workflow for automatic updates on push.
