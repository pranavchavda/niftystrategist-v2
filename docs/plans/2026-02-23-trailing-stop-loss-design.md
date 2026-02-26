# Trailing Stop-Loss Feature Design

**Date:** 2026-02-23
**Status:** Approved (user asked to proceed)
**Origin:** Cockpit thread `cockpit_20260223_8584893e` — user set static stop-losses for 8 portfolio positions, suggested adding trailing capability to the monitor.

## Problem

The trade monitor currently supports static price stop-losses: "sell when price drops to X." These don't adapt as prices rise, leaving gains unprotected. Users must manually ask the agent to "trail higher" to update levels.

A **trailing stop-loss** automatically raises the stop level as the price increases, locking in progressively more profit.

## Design

### New Trigger Type: `trailing_stop`

Follows the existing pattern — new value for `trigger_type` with its own `trigger_config` schema and evaluator function.

### Trigger Config

```python
class TrailingStopTrigger(BaseModel):
    trail_percent: float          # e.g. 15.0 = 15% below peak
    initial_price: float          # price when rule was created (audit trail)
    highest_price: float          # tracked by daemon on each tick, persisted to DB
    reference: Literal["ltp", "bid", "ask", "open", "high", "low"] = "ltp"
```

**Stop level:** `stop_price = highest_price * (1 - trail_percent / 100)`
**Fires when:** `current_price <= stop_price`

### Evaluator (Pure Function)

```python
def evaluate_trailing_stop_trigger(
    rule: MonitorRule,
    market_data: dict,
) -> tuple[bool, dict | None]:
```

Returns `(fired, updated_trigger_config_or_None)`.

- If `current_price > highest_price`: update `highest_price`, recalculate stop. Return `(False, updated_config)`.
- If `current_price <= stop_price`: return `(True, None)`.
- Otherwise: return `(False, None)`.

### RuleResult Extension

Add `trigger_config_update: dict | None = None` to `RuleResult`. The daemon checks this after evaluation and persists changes to DB. This keeps evaluators pure (no I/O).

### Daemon Changes

1. Route `trailing_stop` rules in `_on_tick()` (same as `price` rules — filter by `instrument_token`).
2. After evaluation, if `result.trigger_config_update` is non-None, call `crud.update_rule(rule_id, trigger_config=result.trigger_config_update)`.
3. Also update the in-memory rule object so the next tick uses the new `highest_price` without waiting for the next DB poll.

### UserManager Changes

Add `"trailing_stop"` to `extract_instruments_from_rules()` so the daemon subscribes to market data for these instruments.

### CLI: `nf-monitor add-trailing`

```bash
nf-monitor add-trailing --symbol PIRAMALFIN --qty 5 --trail-percent 15 \
  --product D --max-fires 1 --expires today --json
```

Auto-generates:
- `name`: "{SYMBOL} Trailing SL {trail_percent}%"
- `trigger_type`: "trailing_stop"
- `trigger_config`: `{trail_percent, initial_price: <current LTP>, highest_price: <current LTP>, reference: "ltp"}`
- `action_type`: "place_order"
- `action_config`: `{symbol, transaction_type: "SELL", quantity, order_type: "MARKET", product}`

The CLI fetches the current LTP to set `initial_price` and `highest_price`.

### No DB Schema Changes

`trigger_type` is `VARCHAR(20)`, `trigger_config` is `JSONB`. No migration needed.

### No API Changes

`CreateRuleRequest` already accepts arbitrary `trigger_type` and `trigger_config`. The orchestrator agent or frontend can create trailing stop rules via the existing `POST /api/monitor/rules` endpoint.

## Files to Change

| File | Changes |
|------|---------|
| `monitor/models.py` | Add `TrailingStopTrigger`, update `MonitorRule.trigger_type` Literal |
| `monitor/rule_evaluator.py` | Add `evaluate_trailing_stop_trigger()`, add `trigger_config_update` to `RuleResult`, wire into `evaluate_rule()` |
| `monitor/daemon.py` | Handle `trigger_config_update` persistence, route `trailing_stop` in `_on_tick()` |
| `monitor/user_manager.py` | Add `"trailing_stop"` to instrument extraction |
| `monitor/crud.py` | Add `update_trigger_config()` helper |
| `cli-tools/nf-monitor` | Add `add-trailing` subcommand |
| `tests/monitor/test_rule_evaluator_trailing.py` | New test file |
| `tests/monitor/test_rule_evaluator_toplevel.py` | Add trailing_stop dispatch test |
| `tests/monitor/test_daemon.py` | Add trailing_stop persistence test |

## Out of Scope (YAGNI)

- Frontend Rule Builder UI updates (can use existing API directly)
- Trail by absolute amount (only percent)
- Trail upward for short positions (only downward for longs)
- Notification integrations beyond existing logging
