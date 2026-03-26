# nf-monitor — Trade Monitor (IFTTT-Style Rules Engine)

Create automated trading rules that evaluate against live market data and execute actions. Runs as a background daemon with WebSocket price feeds.

## Key Concepts

- **Rules**: Conditions that trigger actions when met
- **Triggers**: Price, indicator (RSI/SMA/EMA/MACD), time, order_status, compound (AND/OR), trailing_stop
- **Actions**: place_order, cancel_order, cancel_rule
- **OCO**: Linked stop-loss + target pairs where one firing disables the other
- **Daemon**: Separate systemd process that polls rules and subscribes to WebSocket streams

## Subcommands

### add-rule
Create a monitoring rule with trigger and action.

```bash
nf-monitor add-rule --name "..." --symbol SYM --trigger price --condition lte --price 2400 \
  --action place_order --side SELL --qty 10 --product I --max-fires 1 --expires today --json
```

### add-oco
Create a linked OCO pair (stop-loss + target).

```bash
nf-monitor add-oco --symbol SYM --qty 10 --product I --sl 2400 --target 2700 \
  [--side SELL|BUY] [--expires today] --json
```

- `--side SELL` (default): Exits a LONG position
- `--side BUY`: Exits a SHORT position

### add-trailing
Create a trailing stop-loss rule.

```bash
nf-monitor add-trailing --symbol SYM --qty N --trail-percent PCT \
  [--side SELL|BUY] [--product D|I] [--expires today] --json
```

### F&O Option Monitoring
Use `--underlying`, `--expiry`, `--strike`, `--option-type` instead of `--symbol` for option contracts.

```bash
nf-monitor add-oco --underlying BANKNIFTY --expiry 2026-03-12 --strike 48000 --option-type CE \
  --qty 30 --sl 180 --target 260 --product D --json
```

SL/target prices refer to option PREMIUM, not underlying spot.

### list / enable / disable / delete / logs
```bash
nf-monitor list [--active] [--json]
nf-monitor enable|disable|delete RULE_ID [--json]
nf-monitor logs [--rule RULE_ID] [--limit 20] [--json]
```

## Monitor vs GTT

Use `nf-monitor` when you need:
- Indicator-based triggers (RSI, MACD, SMA)
- Compound conditions (AND/OR)
- Time-based triggers
- Complex multi-rule strategies

Use `nf-gtt` when you need:
- Simple price-based stop-loss/target
- Server-side persistence (survives internet outages)
- Set-and-forget with no daemon dependency

## Important

**NEVER run `nf-monitor start` or `nf-monitor stop`** via the orchestrator. The daemon is managed by systemd. Starting via execute_bash creates a conflicting instance.
