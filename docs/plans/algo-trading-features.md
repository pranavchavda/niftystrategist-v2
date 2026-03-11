# Algo Trading Features — Implementation Plan

## Overview

Expand Nifty Strategist from IFTTT-style monitor rules into a proper algo trading platform. The plan is structured in 4 phases, each independently shippable.

---

## Phase 1: Strategy Templates (`nf-strategy`)

**Goal:** Pre-built rule sets for common intraday setups — one command creates multiple linked monitor rules.

### New CLI tool: `backend/cli-tools/nf-strategy`

Subcommands:

| Template | What it creates | Rules generated |
|----------|----------------|-----------------|
| `orb` (Opening Range Breakout) | Entry above/below 15-min range + SL + target + trailing + 3:15 squareoff | 5-6 rules |
| `breakout` | Entry on price level break + SL + trailing stop + time exit | 4 rules |
| `mean-reversion` | RSI oversold entry + overbought exit + SL | 3 rules |
| `vwap-bounce` | Price near VWAP + RSI confirmation entry + SL + target | 3-4 rules |
| `scalp` | Tight entry/exit with trailing + max-fires for repeated entries | 3 rules |

**CLI interface:**
```bash
# Deploy an ORB strategy for RELIANCE
nf-strategy deploy orb --symbol RELIANCE --capital 50000 --risk-percent 2 --product I --json

# List available templates with descriptions
nf-strategy list --json

# Preview rules without creating them (dry-run)
nf-strategy deploy breakout --symbol HDFCBANK --entry 1650 --sl 1630 --target 1690 --dry-run --json

# Remove all rules belonging to a strategy group
nf-strategy teardown --group-id <uuid> --json
```

### Implementation details:

1. **`backend/cli-tools/nf-strategy`** (~400 lines)
   - `list` — prints template catalog
   - `deploy` — calculates entry/SL/target from params, calls `nf-monitor add-rule` for each rule, links them via `group_id` tag in rule metadata
   - `teardown` — finds all rules with matching `group_id`, disables/deletes them
   - `preview` / `--dry-run` — shows what rules would be created without DB writes

2. **Strategy calculation logic** in `backend/strategies/` (new directory):
   - `backend/strategies/templates.py` — template registry + base class
   - `backend/strategies/orb.py` — ORB: fetch first-15-min candle, derive range, calculate entry/SL/target from ATR
   - `backend/strategies/breakout.py` — simple level breakout with R:R-based target
   - `backend/strategies/mean_reversion.py` — RSI-based mean reversion
   - `backend/strategies/vwap_bounce.py` — VWAP proximity + RSI filter
   - `backend/strategies/scalp.py` — tight range scalp template

3. **Monitor rule enhancement** — add optional `group_id` (UUID string) and `strategy_name` fields to `monitor_rules` table:
   - Migration: `backend/migrations/017_add_strategy_group.sql`
   - Update `MonitorRule` model + CRUD

4. **Orchestrator integration** — add `nf-strategy` to the system prompt's CLI tool table so the agent can deploy strategies conversationally:
   - "Set up an ORB strategy for RELIANCE with 50k capital" → agent calls `nf-strategy deploy orb ...`

### Position sizing logic (shared):
- `backend/strategies/sizing.py` — Given capital, risk %, entry, SL → compute quantity
- Used by all templates
- Respects max position size per strategy

---

## Phase 2: Multi-Condition Rules & Morning Scanner

### 2a: Enhanced compound triggers in the monitor

Currently compound triggers exist but are hard to create via CLI. Make them first-class:

```bash
# Buy RELIANCE when RSI < 30 AND price > VWAP AND volume > 1.5x avg
nf-monitor add-rule \
  --name "RELIANCE mean-rev entry" \
  --symbol RELIANCE \
  --trigger compound \
  --operator and \
  --condition "indicator:rsi:lte:30:5m" \
  --condition "price:gte:2420" \
  --condition "indicator:volume_spike:gte:1.5:5m" \
  --action place_order --side BUY --qty 10 --product I \
  --max-fires 1 --expires today --json
```

**Changes:**
- Update `nf-monitor` CLI to parse `--condition` strings into compound trigger config
- Add VWAP as a new indicator in `indicator_engine.py` (needs intraday candles from market open)
- Add Bollinger Bands as indicator (useful for mean reversion)
- Add Supertrend indicator (popular in Indian market algo trading)

### 2b: New CLI tool: `nf-scan` (Morning Scanner)

Scans a watchlist or Nifty 50 for stocks matching configurable criteria. Run it pre-market or at open to find candidates.

```bash
# Scan Nifty 50 for gap-up > 1% with RSI < 40 (oversold gap-up = bounce candidate)
nf-scan --universe nifty50 --filter "gap_up_pct:gte:1" --filter "rsi:lte:40" --json

# Scan for breakout candidates: price near 52-week high + volume spike
nf-scan --universe watchlist --filter "near_52w_high:lte:2%" --filter "volume_spike:gte:2" --json

# Scan + auto-deploy strategy on top N results
nf-scan --universe nifty50 --filter "gap_up_pct:gte:1.5" --top 3 --auto-deploy orb --capital 30000 --json
```

**Implementation:**
- `backend/cli-tools/nf-scan` (~300 lines)
- Fetches quotes for universe, runs filters, ranks by criteria
- `--auto-deploy` calls `nf-strategy deploy` for top results
- Filters: `gap_up_pct`, `gap_down_pct`, `rsi`, `volume_spike`, `near_52w_high`, `near_52w_low`, `atr_pct` (volatility), `sector`

---

## Phase 3: Backtesting Engine

**Goal:** Validate strategies against historical data before risking capital.

### New CLI tool: `nf-backtest`

```bash
# Backtest ORB strategy on RELIANCE, last 30 trading days
nf-backtest --strategy orb --symbol RELIANCE --days 30 --capital 100000 --json

# Backtest custom entry/exit rules
nf-backtest --symbol HDFCBANK --days 60 \
  --entry "rsi:lte:30 AND price:gte:vwap" \
  --exit "rsi:gte:70 OR trailing_stop:1.5%" \
  --capital 100000 --json

# Compare strategies across multiple symbols
nf-backtest --strategy orb,breakout,mean-reversion --symbols RELIANCE,HDFCBANK,INFY --days 30 --json
```

**Output:**
```json
{
  "strategy": "orb",
  "symbol": "RELIANCE",
  "period": "30 days",
  "total_trades": 18,
  "winners": 11,
  "losers": 7,
  "win_rate": 61.1,
  "avg_winner": 1850,
  "avg_loser": -980,
  "profit_factor": 2.89,
  "max_drawdown_pct": 3.2,
  "net_pnl": 13510,
  "return_pct": 13.5,
  "sharpe_ratio": 1.8,
  "max_consecutive_losses": 3,
  "avg_holding_minutes": 45
}
```

### Implementation:

1. **`backend/backtesting/`** (new directory):
   - `engine.py` — `BacktestEngine` class: loads historical candles, simulates candle-by-candle, applies entry/exit logic using the same `rule_evaluator.py` functions (reuse!)
   - `simulator.py` — `TradeSimulator`: tracks open positions, P&L, equity curve, drawdown
   - `metrics.py` — Compute win rate, Sharpe, profit factor, max drawdown, etc.
   - `report.py` — Format results for CLI output (table + JSON)

2. **`backend/cli-tools/nf-backtest`** (~250 lines)
   - Parses strategy name → loads template → gets entry/exit rules
   - Fetches historical OHLCV via `nf-quote` (or direct Upstox API for larger datasets)
   - Runs `BacktestEngine.run()`
   - Outputs metrics

3. **Key design: Reuse rule evaluator**
   - The same `evaluate_price_trigger`, `evaluate_indicator_trigger`, etc. functions used by the live monitor are used by the backtester
   - This ensures backtest results match live behavior
   - `indicator_engine.compute_indicator()` works on historical candles identically

4. **Data limitations:**
   - Upstox provides up to 1 year of daily candles and ~30 days of intraday
   - For longer backtests, we'd need a data caching layer (future enhancement)
   - Initial version works within Upstox API limits

---

## Phase 4: Multi-Leg Options Strategies

**Goal:** Strategy templates for options (straddles, strangles, iron condors, spreads).

### Extend `nf-strategy` with options templates:

```bash
# Deploy a short straddle on BANKNIFTY
nf-strategy deploy straddle --underlying BANKNIFTY --expiry 2026-03-12 \
  --capital 200000 --adjustment-trigger 30% --json

# Iron condor with auto SL
nf-strategy deploy iron-condor --underlying NIFTY --expiry 2026-03-20 \
  --width 200 --capital 150000 --max-loss 5000 --json

# Bull call spread
nf-strategy deploy bull-spread --underlying RELIANCE --expiry 2026-03-26 \
  --bias bullish --capital 50000 --json
```

### New templates:
| Template | Legs | Monitor rules created |
|----------|------|----------------------|
| `straddle` | ATM CE + ATM PE (sell) | SL per leg, combined SL, time exit |
| `strangle` | OTM CE + OTM PE (sell) | SL per leg, combined SL, adjustment trigger |
| `iron-condor` | 4 legs (OTM sell + further OTM buy, both sides) | SL, max loss exit, time exit |
| `bull-spread` | Buy lower strike CE + sell higher strike CE | SL, target, time exit |
| `bear-spread` | Buy higher strike PE + sell lower strike PE | SL, target, time exit |

### Implementation:
- `backend/strategies/options/` — new subdirectory for options strategy templates
- Uses `nf-options plan` for strike selection + `nf-options charges` for cost estimation
- Creates monitor rules that track **option contract prices** (not underlying)
- `nf-monitor` already supports F&O instrument tokens via `instrument_token` field

---

## Implementation Order & Dependencies

```
Phase 1 (Strategy Templates)      ← START HERE
  ├── strategies/ module
  ├── nf-strategy CLI
  ├── migration 017
  └── orchestrator integration
        │
Phase 2 (Scanner + Compound)      ← builds on Phase 1 templates
  ├── nf-scan CLI
  ├── new indicators (VWAP, BB, Supertrend)
  └── compound CLI syntax
        │
Phase 3 (Backtesting)             ← reuses Phase 1 templates + Phase 2 indicators
  ├── backtesting/ engine
  └── nf-backtest CLI
        │
Phase 4 (Options Strategies)      ← extends Phase 1 with F&O
  ├── strategies/options/
  └── multi-leg order management
```

## Phase 1 File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `backend/strategies/__init__.py` | Create | Package init |
| `backend/strategies/templates.py` | Create | Base class + template registry |
| `backend/strategies/sizing.py` | Create | Position sizing calculator |
| `backend/strategies/orb.py` | Create | ORB strategy template |
| `backend/strategies/breakout.py` | Create | Breakout strategy template |
| `backend/strategies/mean_reversion.py` | Create | Mean reversion template |
| `backend/strategies/vwap_bounce.py` | Create | VWAP bounce template |
| `backend/strategies/scalp.py` | Create | Scalp template |
| `backend/cli-tools/nf-strategy` | Create | Strategy CLI tool |
| `backend/migrations/017_add_strategy_group.sql` | Create | Add group_id + strategy_name columns |
| `backend/monitor/models.py` | Edit | Add group_id, strategy_name fields |
| `backend/monitor/crud.py` | Edit | Support group_id in queries |
| `backend/agents/orchestrator.py` | Edit | Add nf-strategy to system prompt |
| `backend/tests/strategies/` | Create | Tests for templates + sizing |

---

## Open Questions

1. **VWAP data source** — Upstox doesn't provide VWAP directly. We'd compute it from intraday candles (cumulative `(price × volume) / total_volume`). Good enough for 5m timeframes.
2. **Paper trading mode** — The monitor daemon already has `paper_mode`. Should strategies also have a paper-only flag for testing?
3. **Strategy P&L tracking** — Should we track strategy-level P&L (aggregate across all rules in a group) or rely on the existing per-trade tracking?
4. **Notifications** — Should fired strategy rules send push/email notifications? (Currently monitor rules just log.)
