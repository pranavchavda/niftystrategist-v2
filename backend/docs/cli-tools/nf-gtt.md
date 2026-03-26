# nf-gtt — GTT (Good Till Triggered) Orders

Server-side persistent orders that trigger automatically when price conditions are met. Unlike `nf-monitor` rules (which are client-side and require the daemon to be running), GTT orders are stored on Upstox's servers and survive app restarts, disconnections, and server downtime.

## Key Concepts

- **GTT vs Monitor**: GTT is broker-native (Upstox handles it). Monitor is our daemon-based system. GTT is simpler but less flexible (no indicators, no compound conditions). Use GTT for simple stop-losses and targets. Use Monitor for complex rules.
- **SINGLE**: One trigger condition (entry OR stoploss)
- **MULTIPLE (OCO)**: Two trigger conditions — target + stoploss. When one fires, the other is automatically cancelled.
- **Trigger types**: `ABOVE` (fires when price rises above trigger), `BELOW` (fires when price drops below trigger), `IMMEDIATE`
- **Auto-detection**: The CLI automatically sets ABOVE/BELOW based on the strategy and side. BUY entry = BELOW (dip buy), SELL stoploss = BELOW, SELL target = ABOVE.

## Subcommands

### place
Place a GTT order.

```bash
# Single entry GTT (buy when price drops to 1200)
nf-gtt place RELIANCE BUY 10 --trigger 1200

# Stoploss GTT (sell when price drops to 3200)
nf-gtt place TCS SELL 5 --stoploss 3200

# OCO: target + stoploss (whichever hits first)
nf-gtt place INFY SELL 10 --target 1800 --stoploss 1500

# Trailing trigger (trigger moves with price, gap of 20 points)
nf-gtt place RELIANCE BUY 10 --trigger 1400 --trailing 20

# With explicit trigger direction
nf-gtt place RELIANCE BUY 10 --trigger 1400 --trigger-type ABOVE  # breakout buy
```

Options:
- `--product D|I` — D=Delivery/NRML (default), I=Intraday/MIS
- `--trigger-type auto|ABOVE|BELOW|IMMEDIATE` — Default: auto-detected

### list
Show all GTT orders (active, triggered, cancelled).

```bash
nf-gtt list [--json]
```

### modify
Modify an existing GTT order's trigger price or quantity.

```bash
nf-gtt modify GTT_ID --trigger 1250
nf-gtt modify GTT_ID --quantity 20
nf-gtt modify GTT_ID --trigger 1250 --trigger-type ABOVE
```

Automatically fetches the existing order to preserve fields you don't change.

### cancel
Cancel a pending GTT order.

```bash
nf-gtt cancel GTT_ID
```

## GTT vs nf-monitor Comparison

| Feature | nf-gtt | nf-monitor |
|---------|--------|------------|
| Execution | Server-side (Upstox) | Client-side (daemon) |
| Survives restarts | Yes | Yes (daemon auto-restarts) |
| Survives no internet | Yes | No |
| Price triggers | Yes | Yes |
| Indicator triggers (RSI, MACD) | No | Yes |
| Compound conditions (AND/OR) | No | Yes |
| Trailing stop | Yes (trailing_gap) | Yes (trail_percent) |
| OCO (one-cancels-other) | Yes (built-in) | Yes (linked rules) |
| Time triggers | No | Yes |
| Max fires | 1 (always) | Configurable |
| Expiry | ~1 year | Configurable |
