# Nifty Strategist CLI Tools

CLI tools for stock market data and trading operations. Run from `backend/` directory.

## Quick Reference

| Tool | Description | Needs Token | Example |
|------|-------------|-------------|---------|
| `nf-market-status` | Check if NSE market is open/closed | No | `python cli-tools/nf-market-status` |
| `nf-quote` | Get live quotes and historical data | Yes | `python cli-tools/nf-quote RELIANCE` |
| `nf-analyze` | Technical analysis (RSI, MACD, signals) | Yes | `python cli-tools/nf-analyze RELIANCE` |
| `nf-portfolio` | View holdings, positions, P&L | Yes | `python cli-tools/nf-portfolio` |
| `nf-order` | Place, list, cancel orders | Yes | `python cli-tools/nf-order buy RELIANCE 10` |
| `nf-watchlist` | Manage watchlist with price alerts | Yes | `python cli-tools/nf-watchlist` |

All tools support `--json` for structured output and `--help` for usage info.

---

## Tool Details

### nf-market-status

Check NSE market status — whether market is open, closed, or in pre-open session.

```
python cli-tools/nf-market-status [--json]
```

**Examples:**
```bash
python cli-tools/nf-market-status          # Human-readable status
python cli-tools/nf-market-status --json   # JSON output
```

- No API token needed (pure time-based calculation)
- Accounts for weekends and NSE holidays (2026 calendar)

---

### nf-quote

Get live stock quotes or historical OHLCV candlestick data.

```
python cli-tools/nf-quote SYMBOL [SYMBOL2 ...] [--json] [--historical --interval INTERVAL --days N]
python cli-tools/nf-quote --list
python cli-tools/nf-quote --search TERM
```

**Examples:**
```bash
python cli-tools/nf-quote RELIANCE                          # Live quote
python cli-tools/nf-quote GOLDBEES --json                   # Any NSE symbol (ETF, etc.)
python cli-tools/nf-quote RELIANCE TCS INFY --json          # Multiple quotes, JSON
python cli-tools/nf-quote HDFCBANK --historical --days 5    # Daily OHLCV
python cli-tools/nf-quote TCS --historical --interval 15minute --days 5
python cli-tools/nf-quote --list                            # Nifty 50 symbols
python cli-tools/nf-quote --search GOLD                     # Search any NSE stock
python cli-tools/nf-quote --search "HDFC"                   # Find all HDFC variants
```

- Supports all 8000+ NSE symbols (not just Nifty 50)
- Non-Nifty 50 symbols show an info note
- Intervals: `1minute`, `5minute`, `15minute`, `30minute`, `day`

---

### nf-analyze

Technical analysis with RSI, MACD, moving averages, and trading signals.

```
python cli-tools/nf-analyze SYMBOL [--interval 15minute|30minute|day] [--json]
python cli-tools/nf-analyze SYMBOL1 SYMBOL2 ... --compare [--json]
```

**Examples:**
```bash
python cli-tools/nf-analyze RELIANCE                       # Full analysis (15min)
python cli-tools/nf-analyze HDFCBANK --interval day         # Daily timeframe
python cli-tools/nf-analyze RELIANCE TCS INFY --compare     # Compare signals
python cli-tools/nf-analyze RELIANCE --json                 # JSON output
```

- Returns: signal (buy/sell/hold), confidence, RSI, MACD, trend, support/resistance
- Compare mode ranks multiple stocks side-by-side

---

### nf-portfolio

View portfolio holdings, specific positions, or calculate position sizes.

```
python cli-tools/nf-portfolio [--json]
python cli-tools/nf-portfolio --position SYMBOL [--json]
python cli-tools/nf-portfolio --calc-size SYMBOL --risk AMOUNT --sl PERCENT [--json]
```

**Examples:**
```bash
python cli-tools/nf-portfolio                                  # Full portfolio
python cli-tools/nf-portfolio --position RELIANCE              # Single position
python cli-tools/nf-portfolio --calc-size RELIANCE --risk 5000 --sl 2  # Position sizing
python cli-tools/nf-portfolio --json                           # JSON output
```

- Position size calculator uses risk amount and stop-loss % to recommend quantity

---

### nf-order

Place buy/sell orders, view order book, or cancel orders.

```
python cli-tools/nf-order buy SYMBOL QUANTITY [--type MARKET|LIMIT] [--price P] [--sl P] [--target P] [--dry-run] [--json]
python cli-tools/nf-order sell SYMBOL QUANTITY [--type MARKET|LIMIT] [--price P] [--json]
python cli-tools/nf-order list [--all] [--limit N] [--json]
python cli-tools/nf-order cancel ORDER_ID [--json]
```

**Examples:**
```bash
python cli-tools/nf-order buy RELIANCE 10                      # Market buy
python cli-tools/nf-order buy RELIANCE 10 --type LIMIT --price 1450  # Limit buy
python cli-tools/nf-order buy RELIANCE 10 --dry-run             # Preview only
python cli-tools/nf-order sell TCS 5                             # Market sell
python cli-tools/nf-order list                                   # Open orders
python cli-tools/nf-order list --all                             # All recent orders
python cli-tools/nf-order cancel abc123                          # Cancel order
```

- `--dry-run` previews the order without executing
- `buy` and `cancel` are HITL-protected when called from the orchestrator

---

### nf-watchlist

Manage stock watchlist with price target alerts. Requires `NF_USER_ID` env var.

```
python cli-tools/nf-watchlist [--json]
python cli-tools/nf-watchlist add SYMBOL [--buy P] [--sell P] [--notes "..."] [--json]
python cli-tools/nf-watchlist remove SYMBOL [--json]
python cli-tools/nf-watchlist update SYMBOL [--buy P] [--sell P] [--notes "..."] [--clear-targets] [--json]
python cli-tools/nf-watchlist alerts [--json]
```

**Examples:**
```bash
python cli-tools/nf-watchlist                                   # Show watchlist
python cli-tools/nf-watchlist add RELIANCE --buy 1400 --sell 1600  # Add with targets
python cli-tools/nf-watchlist add TCS --notes "Wait for earnings"  # Add with notes
python cli-tools/nf-watchlist remove RELIANCE                    # Remove
python cli-tools/nf-watchlist update RELIANCE --buy 1380         # Update target
python cli-tools/nf-watchlist alerts                             # Check alerts only
```

- Shows live prices and change since added
- Triggers alerts when current price crosses target buy/sell levels
