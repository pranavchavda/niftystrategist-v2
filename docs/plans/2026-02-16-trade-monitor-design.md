# Trade Monitor Daemon + Intraday Order Fix

**Date:** 2026-02-16
**Status:** Approved

## Problem

1. **Intraday orders placed as delivery:** `product="D"` hardcoded in `upstox_client.py:615`. No `--product` flag on `nf-order`. Users pay full margin for what should be intraday trades.
2. **No trade monitoring:** After placing an order, the system has no way to enforce stop-losses, targets, time-based exits, or react to order status changes. The DB schema has `stop_loss`/`target_price` fields on Trade but nothing evaluates them.

## Fix 1: Intraday Order Support

- Add `--product {D,I}` flag to `nf-order` CLI (default: `D`)
- Pass through to `UpstoxClient.place_order()` as a parameter
- Update orchestrator system prompt: if user says "intraday"/"scalp"/"day trade" → use `--product I`
- Warn about auto-square-off at 3:15-3:25 PM IST for intraday orders

## Fix 2: Trade Monitor Daemon (`nf-monitor`)

### Architecture

Standalone Python daemon process, separate from the FastAPI backend. Reuses backend code (`UpstoxClient`, DB models, `technical_analysis` service). Runs as a systemd service.

```
nf-monitor (standalone daemon)
├── UserManager
│   ├── Per-user lifecycle (start/stop connections)
│   └── Auth token refresh
├── Per-User Session
│   ├── PortfolioStream (WebSocket) — order/position/holding updates
│   ├── MarketDataStream (WebSocket, protobuf) — live prices
│   └── RuleEvaluator — evaluates rules on every tick/timer/event
├── IndicatorEngine — RSI, MACD, MA from buffered candle data
├── ActionExecutor — places/cancels orders, logs to MonitorLog
└── DB Poller (30s) — picks up new/modified/deleted rules
```

**Key decisions:**
- One set of WS connections per active user (has ≥1 enabled rule)
- Rules stored in DB (`MonitorRule` table), created by orchestrator CLI or Rule Builder UI
- Daemon polls DB every 30s for rule changes (no direct IPC)
- Dynamic market data subscriptions (only instruments with active rules)
- Indicator computation uses buffered ticks → aggregated candles + historical seed data via REST

### Data Model

#### MonitorRule table

| Column | Type | Description |
|--------|------|-------------|
| id | int PK | |
| user_id | int FK | Owner |
| name | varchar | Human-readable label |
| enabled | bool | Toggle without deleting |
| trigger_type | enum | `price`, `time`, `indicator`, `order_status`, `compound` |
| trigger_config | jsonb | Trigger-specific parameters |
| action_type | enum | `place_order`, `cancel_order`, `modify_order`, `cancel_rule` |
| action_config | jsonb | Action-specific parameters |
| instrument_token | varchar | Upstox instrument key (nullable) |
| symbol | varchar | Display symbol |
| linked_trade_id | int FK | Optional Trade link |
| linked_order_id | varchar | Optional Upstox order ID |
| fire_count | int | Times fired |
| max_fires | int | Auto-disable after N fires (1=one-shot, null=unlimited) |
| expires_at | timestamp | Auto-disable time |
| created_at | timestamp | |
| updated_at | timestamp | |
| fired_at | timestamp | Last fire time |

#### Trigger configs

**Price:** `{"condition": "lte|gte|crosses_above|crosses_below", "price": 2400.0, "reference": "ltp|bid|ask|open|high|low"}`

**Time:** `{"at": "15:15", "on_days": ["mon",...], "market_only": true}`

**Indicator:** `{"indicator": "rsi|macd|ema_crossover|volume_spike", "timeframe": "5m", "condition": "lte|gte", "value": 30, "params": {"period": 14}}`

**Order status:** `{"order_id": "...", "status": "complete|rejected|cancelled|partially_filled"}`

**Compound:** `{"operator": "and|or", "conditions": [...]}`

#### Action configs

**Place order:** `{"symbol": "...", "transaction_type": "BUY|SELL", "quantity": 10, "order_type": "MARKET|LIMIT", "product": "I|D", "price": null}`

**Cancel order:** `{"order_id": "..."}`

**Cancel rule (OCO):** `{"rule_id": 42}`

#### MonitorLog table

| Column | Type | Description |
|--------|------|-------------|
| id | int PK | |
| user_id | int FK | |
| rule_id | int FK | |
| trigger_snapshot | jsonb | Market state at trigger time |
| action_taken | varchar | |
| action_result | jsonb | Order response / error |
| created_at | timestamp | |

### WebSocket Connections

**Portfolio Stream:** JSON format, `update_types=order,position,holding`. Triggers `order_status` rules.

**Market Data Feed V3:** Protobuf format, `ltpc` mode. Dynamic instrument subscriptions.

**Reconnection:** Exponential backoff (1s→60s max). On 401: refresh token. On refresh failure: mark user monitoring paused.

**Heartbeat:** Expect data/ping every 30s. Self-ping if silent. Reconnect if no pong in 10s.

### CLI Tool: `nf-monitor`

```bash
nf-monitor add-rule --name "..." --symbol SYM --trigger price --condition lte --price 2400 --action place_order --side SELL --qty 10 --product I --max-fires 1 --expires today --json
nf-monitor add-oco --symbol SYM --qty 10 --product I --sl 2400 --target 2700 --linked-trade TX --expires today --json
nf-monitor add-rule --trigger time --at 15:15 --action square_off_intraday --expires today --json
nf-monitor list [--active] [--json]
nf-monitor disable|enable|delete RULE_ID
nf-monitor logs [--rule RULE_ID] [--limit 20] [--json]
nf-monitor status [--json]
```

### Orchestrator Integration

After placing an intraday order, the orchestrator:
1. Creates OCO rules (SL + target) via `nf-monitor add-oco`
2. Creates auto-square-off rule at 15:15 IST
3. Reports the setup to the user

### Rule Builder UI

Visual IFTTT-style interface in the frontend. Both the UI and the orchestrator write to the same `MonitorRule` table. Design TBD — separate design doc.

### Testing Strategy

1. **Unit tests:** Rule evaluation, indicator computation, compound triggers, OCO linking, expiry, candle aggregation. No network/DB.
2. **Integration tests:** Mock WebSocket server replaying recorded/synthetic data. Test SL fires, target fires, reconnection, duplicate prevention, token expiry.
3. **Paper trading E2E:** Real Upstox WebSocket feeds + paper trading engine for execution. Run 2-3 full sessions before going live.
4. **Replay testing:** Record real WS sessions, replay at accelerated speed for regression testing.
5. **CLI test commands:** `nf-monitor start --paper`, `nf-monitor replay --session FILE --speed 100x`, `nf-monitor simulate --symbol SYM --price P`, `nf-monitor dry-run`

### Go-Live Checklist

1. Unit tests pass for all rule types
2. Mock WS integration tests pass (including edge cases)
3. Paper mode for 2-3 trading sessions, logs reviewed
4. `dry-run` against real positions
5. Live test with small position + tight SL
