# nf-watchlist — Watchlist with Price Alerts

Manage a personal stock watchlist with buy/sell target prices and live price tracking.

## Subcommands

### Default (no subcommand)
Show watchlist with live prices and alert status.

```bash
nf-watchlist [--json]
```

### add
Add a stock to the watchlist with optional target prices.

```bash
nf-watchlist add SYMBOL [--buy PRICE] [--sell PRICE] [--notes "..."]
```

### remove
Remove a stock from the watchlist.

```bash
nf-watchlist remove SYMBOL
```

### update
Update buy/sell targets or notes for an existing watchlist entry.

```bash
nf-watchlist update SYMBOL [--buy P] [--sell P] [--notes "..."] [--clear-targets]
```

### alerts
Check which watchlist items have triggered price alerts.

```bash
nf-watchlist alerts [--json]
```

## Examples

```bash
nf-watchlist add RELIANCE --buy 1350 --sell 1500 --notes "Wait for support"
nf-watchlist add TCS --sell 3800    # Only sell target
nf-watchlist                         # See all with live prices
nf-watchlist alerts                  # Which targets are hit?
nf-watchlist update RELIANCE --buy 1300  # Lower buy target
nf-watchlist remove TCS
```

## When to use
- **Tracking stocks of interest**: Add with targets, check periodically
- **Simple price alerts**: Set buy/sell levels, check with `alerts`
- **For automated triggers**: Use `nf-monitor` or `nf-gtt` instead (they execute orders automatically)
