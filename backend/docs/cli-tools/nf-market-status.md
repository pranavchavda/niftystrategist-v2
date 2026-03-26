# nf-market-status — Market Status, Holidays & Timings

Check NSE market status, upcoming holidays, and exchange session timings.

## Subcommands

### Default (no flags)
Check if the market is currently open or closed.

```bash
nf-market-status [--json]
```

Shows: open/closed/pre-open status, time to next event, source (Upstox API or time-based fallback).

### --holidays
Show all market holidays for the current year.

```bash
nf-market-status --holidays [--json]        # All holidays this year
nf-market-status --holidays 2026-03-30      # Check if a specific date is a holiday
```

Output shows:
- Date, description, holiday type (Trading Holiday vs Settlement Holiday)
- Closed exchanges (NSE, NFO, BSE, etc.)
- Past holidays marked with checkmark
- Trading holidays (red) vs settlement-only holidays (yellow)

**Trading Holiday** = Exchange fully closed, no trading possible
**Settlement Holiday** = Trading may occur but settlement is delayed

### --timings
Show exchange open/close times for a specific date.

```bash
nf-market-status --timings 2026-03-27 [--json]
```

Shows all exchanges (NSE, BSE, NFO, MCX, CDS, etc.) with their IST open/close times for that date. Useful for understanding pre-market, post-market, and commodity trading sessions.

## When to use

- **Before placing orders**: Check if market is open to avoid AMO confusion
- **Planning ahead**: Check holidays before scheduling awakenings or monitor rules
- **Session awareness**: MCX trades until 11:30 PM, NSE closes at 3:30 PM
- **Holiday check**: "Is the market open on Holi?" → `nf-market-status --holidays 2026-03-03`
