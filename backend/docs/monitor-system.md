# Trade Monitor System

An IFTTT-style rule engine that evaluates user-defined trigger conditions against live market data and executes trading actions automatically.

## Architecture

```
FastAPI (web)                        MonitorDaemon (separate process)
|-- REST API: /api/monitor/*         |-- Polls DB for active rules (30s)
|-- Rule Builder UI: /monitor        |-- Opens Upstox WebSocket streams
|-- Symbol search autocomplete       |-- Evaluates triggers on each tick
                                     |-- Fires actions (place/cancel orders)
```

### Key Files

| Component | Path |
|-----------|------|
| Rule models | `monitor/models.py` |
| Rule evaluator | `monitor/rule_evaluator.py` |
| Daemon main loop | `monitor/daemon.py` |
| Action executor | `monitor/action_executor.py` |
| Per-user sessions | `monitor/user_manager.py` |
| Candle aggregation | `monitor/candle_buffer.py` |
| Indicator engine | `monitor/indicator_engine.py` |
| DB CRUD | `monitor/crud.py` |
| Market data stream | `monitor/streams/market_data.py` |
| Portfolio stream | `monitor/streams/portfolio.py` |
| WebSocket base | `monitor/streams/connection.py` |
| REST API | `api/monitor.py` |
| CLI tool | `cli-tools/nf-monitor` |
| Frontend UI | `frontend-v2/app/routes/monitor.tsx` |
| DB migration | `migrations/014_add_monitor_tables.sql` |
| Tests | `tests/monitor/` (67+ tests) |

## Trigger Types

### price

Fires when a stock price meets a condition.

| Config Field | Values |
|-------------|--------|
| `condition` | `lte`, `gte`, `crosses_above`, `crosses_below` |
| `price` | Target price value |
| `reference` | `ltp`, `bid`, `ask`, `open`, `high`, `low` |

`crosses_*` conditions require a previous tick for comparison (first tick after creation cannot cross).

### indicator

Fires when a technical indicator meets a condition. Evaluated on candle completion only.

| Config Field | Values |
|-------------|--------|
| `indicator` | `rsi`, `macd`, `ema_crossover`, `volume_spike` |
| `timeframe` | `1m`, `5m`, `15m`, `30m`, `1h`, `1d` |
| `condition` | `lte`, `gte`, `crosses_above`, `crosses_below` |
| `value` | Target indicator value |

Indicators computed via `indicator_engine.py` using pandas + ta library:
- **RSI** — period 14, value 0-100, needs 15 candles
- **MACD** — histogram or line, needs 26 candles
- **EMA Crossover** — fast(12)/slow(26) EMA diff, needs 26 candles
- **Volume Spike** — current vol / 20-candle avg ratio

### time

Fires at a specific time.

| Config Field | Values |
|-------------|--------|
| `at` | `HH:MM` in IST |
| `on_days` | List of weekday numbers |
| `market_only` | Only fire during market hours |

60-second tolerance window. IST timezone for evaluation.

### order_status

Fires when an order reaches a specific status.

| Config Field | Values |
|-------------|--------|
| `order_id` | Upstox order ID to watch |
| `status` | `complete`, `rejected`, `cancelled`, `partially_filled` |

Evaluated from portfolio WebSocket stream events.

### compound

Combines multiple conditions with AND/OR logic.

| Config Field | Values |
|-------------|--------|
| `operator` | `and`, `or` |
| `conditions` | List of sub-conditions (price, time, indicator, order_status) |

### trailing_stop

A stop-loss that tracks the best price and fires on retracement.

| Config Field | Values |
|-------------|--------|
| `trail_percent` | Percentage trail from best price |
| `initial_price` | Starting price |
| `highest_price` / `lowest_price` | Best price seen (auto-updated) |
| `direction` | `long` or `short` |

`highest_price`/`lowest_price` is persisted to `trigger_config` after each tick to survive daemon restarts.

## Action Types

### place_order

Places a real order via Upstox.

| Config Field | Values |
|-------------|--------|
| `symbol` | NSE symbol |
| `transaction_type` | `BUY`, `SELL` |
| `quantity` | Number of shares |
| `order_type` | `MARKET`, `LIMIT` |
| `product` | `D` (delivery), `I` (intraday) |
| `price` | Limit price (optional) |

### cancel_order

Cancels an existing order by ID.

### cancel_rule

Disables another rule in the database. Used to implement OCO pairs.

## OCO (One-Cancels-Other) Pairs

Linked stop-loss + target rules where one firing disables the other.

**Creation** (via `POST /api/monitor/oco` or `nf-monitor add-oco`):
1. Create SL rule (place_order action)
2. Create Target rule (place_order action + linked `cancel_rule` for SL)
3. Update SL rule with linked `cancel_rule` for Target

Both rules have `max_fires=1`. When either fires, the ActionExecutor disables the other.

**Directionality:**
- **Long exit** (`--side SELL`): SL condition=lte (price drops), Target condition=gte (price rises)
- **Short exit** (`--side BUY`): SL condition=gte (price rises), Target condition=lte (price drops)

## Daemon

### Lifecycle

```
MonitorDaemon
  |-- _poll_rules()           # Every 30s: load rules from DB, sync user sessions
  |-- _on_tick()              # On each market tick: evaluate price/indicator/trailing rules
  |-- _on_portfolio_event()   # On order updates: evaluate order_status rules
  |-- _check_time_rules()     # Periodically: evaluate time-based rules
  |-- _evaluate_and_execute() # Rule fired -> log + execute action + disable linked rules
```

### Per-User Sessions (`user_manager.py`)

Each user with active rules gets a `UserSession` containing:
- Two WebSocket streams (market data + portfolio)
- Candle buffers per instrument/timeframe
- Previous prices (for `crosses_*` detection)
- Indicator values and previous indicator values

**Session lifecycle:**
- `start_user(user_id, token, rules)` — opens streams, subscribes to instruments
- `sync_rules(user_id, rules)` — updates subscriptions, rebuilds candle buffers
- `stop_user(user_id)` — closes streams

### WebSocket Streams

**Market Data** (`streams/market_data.py`):
- Upstox `/v3/feed/market-data-feed`
- Protocol: WebSocket + protobuf (binary OHLCV + depth)
- Data: ltp, close, volume, open, high, low, oi, iv

**Portfolio** (`streams/portfolio.py`):
- Upstox `/v2/feed/portfolio-stream-feed`
- Protocol: WebSocket + JSON
- Events: order status changes, positions, holdings

**Connection management** (`streams/connection.py`):
- Exponential backoff reconnection (1s → 2s → 4s ... max 60s)
- Auth failure triggers TOTP refresh callback

### Candle Buffering (`candle_buffer.py`)

Aggregates price ticks into OHLCV candles:
- Configurable timeframe (1m, 5m, 15m, 30m, 1h, 1d)
- Max 200 candles stored (deque)
- `add_tick(price, volume, timestamp)` — updates current or starts new candle
- `get_completed_candles()` — excludes incomplete current candle (for indicator computation)

### Token Management

- Loads tokens via `get_user_upstox_token(user_id)` on each poll
- Auto-refreshes via TOTP if credentials saved
- Skips users with expired tokens and no TOTP credentials
- 30-minute cooldown after failed refresh

### Paper Mode

Actions logged but not executed. Set via daemon constructor flag or `--paper` CLI option.

## Evaluation Flow

```
Market Tick arrives
  |-> UserManager._on_market_tick()
  |   |-> Feed tick to candle buffers
  |   |-> Detect candle completion -> recompute indicators
  |   |-> Call daemon._on_tick() with tick data
  |   |-> Update prev_prices
  |
  |-> Daemon._on_tick()
      |-> For each price/indicator/compound/trailing rule matching instrument:
          |-> evaluate_rule(rule, context)
          |   |-> Check enabled, not expired, under max_fires
          |   |-> Dispatch to trigger evaluator
          |   |-> Return RuleResult (fired?, action, rules_to_cancel, config_update)
          |
          |-> If fired:
              |-> Persist trigger_config updates (trailing stop best price)
              |-> Increment fire_count
              |-> ActionExecutor.execute() -> place_order / cancel_order / cancel_rule
              |-> Disable linked OCO rules
              |-> Log to monitor_logs
```

## CLI Tool (`nf-monitor`)

| Command | Purpose | Example |
|---------|---------|---------|
| `add-rule` | Create single rule | `nf-monitor add-rule --name "SL" --symbol RELIANCE --trigger price --condition lte --price 2400 --action place_order --side SELL --qty 10` |
| `add-oco` | Create OCO pair | `nf-monitor add-oco --symbol RELIANCE --qty 10 --sl 2400 --target 2700 --side SELL --expires today` |
| `add-trailing` | Create trailing stop | `nf-monitor add-trailing --symbol RELIANCE --qty 10 --trail-percent 15 --side SELL --expires today` |
| `list` | List rules | `nf-monitor list --active --json` |
| `enable` | Enable rule | `nf-monitor enable 5` |
| `disable` | Disable rule | `nf-monitor disable 5` |
| `delete` | Delete rule | `nf-monitor delete 5` |
| `logs` | View firing history | `nf-monitor logs --rule 5 --limit 20 --json` |
| `start` | Run daemon | `nf-monitor start --paper --poll-interval 10` |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/monitor/symbols` | Symbol autocomplete |
| GET | `/api/monitor/rules` | List rules (optional `?active=true`) |
| POST | `/api/monitor/rules` | Create rule |
| PATCH | `/api/monitor/rules/{id}` | Update rule |
| DELETE | `/api/monitor/rules/{id}` | Delete rule |
| POST | `/api/monitor/oco` | Create OCO pair |
| GET | `/api/monitor/logs` | Firing history |

**Timezone handling:** Frontend sends ISO strings with `Z`. The `_strip_tz()` helper strips tzinfo before DB insert (columns are naive TIMESTAMP).

## Database Schema

**Table:** `monitor_rules`
```
id, user_id, name, enabled
trigger_type, trigger_config (JSONB)
action_type, action_config (JSONB)
instrument_token, symbol
fire_count, max_fires, expires_at, fired_at
linked_trade_id, linked_order_id
created_at, updated_at
```

**Table:** `monitor_logs`
```
id, rule_id, user_id
trigger_snapshot (JSONB), action_result (JSONB)
fired_at
```

**Indexes:** `(user_id, enabled)`, `(instrument_token)`, `(symbol)`

## Deployment

The daemon needs its own systemd unit (separate from FastAPI). Currently started manually via `nf-monitor start`. Token loading happens on each poll cycle via the same `get_user_upstox_token()` used by all other systems.
