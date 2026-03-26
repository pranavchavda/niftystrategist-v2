# nf-trades — Trades, P&L Reports & Charges

View today's executed trades, historical trade data, trade-wise P&L reports, and charges breakdowns.

## Subcommands

### Default (no subcommand)
Show today's executed trades.

```bash
nf-trades [--json]
```

### history
Historical trades with date range and pagination.

```bash
nf-trades history [--segment EQ|FO] [--days 30] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--page N] [--page-size N] [--json]
```

### charges
Trade charges breakdown (brokerage, STT, GST, stamp duty, etc.).

```bash
nf-trades charges [--segment EQ|FO] [--days N] [--from DD-MM-YYYY] [--to DD-MM-YYYY] [--fy 2526] [--json]
```

**Default**: Today only (`--days 1`). Use `--days 7` for weekly, `--days 30` for monthly.

**Important**: Charges data is T+1 (available next trading day). Today's charges will show ₹0.

```bash
nf-trades charges                    # Today only (likely ₹0 if no T+1 data yet)
nf-trades charges --days 7           # Last 7 days
nf-trades charges --days 30          # Last 30 days
nf-trades charges --segment FO       # F&O charges only
```

### report
Trade-wise P&L report with buy/sell averages and net profit/loss per scrip.

```bash
nf-trades report [--segment EQ|FO] [--page N] [--page-size N] [--fy 2526] [--json]
```

Shows: scrip name, quantity, buy average, sell average, P&L per trade, date. Includes totals (total buy, total sell, net P&L).

```bash
nf-trades report                     # Current FY, page 1
nf-trades report --page-size 50      # More results per page
nf-trades report --segment FO        # F&O trades only
nf-trades report --fy 2425           # Previous financial year
```

## Common Questions

| Question | Command |
|----------|---------|
| What did I trade today? | `nf-trades` |
| How much did I pay in charges this week? | `nf-trades charges --days 7` |
| What's my overall P&L this FY? | `nf-trades report` |
| Show me F&O charges for March | `nf-trades charges --segment FO --from 01-03-2026 --to 31-03-2026` |
