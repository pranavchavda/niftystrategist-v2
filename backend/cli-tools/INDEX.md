# Nifty Strategist CLI Tools

CLI tools for stock market data and trading operations. Run from `backend/` directory.

## Quick Reference

| Tool | Description | Needs Token | Example |
|------|-------------|-------------|---------|
| `nf-market-status` | Check if NSE market is open/closed | No | `python cli-tools/nf-market-status` |
| `nf-quote` | Get live quotes and historical data | Yes | `python cli-tools/nf-quote RELIANCE` |
| `nf-analyze` | Technical analysis (RSI, MACD, signals) | Yes | `python cli-tools/nf-analyze RELIANCE` |
| `nf-portfolio` | View holdings, positions, P&L | Yes | `python cli-tools/nf-portfolio` |
| `nf-funds` | Available margin, buying power | Yes | `python cli-tools/nf-funds` |
| `nf-profile` | User profile, active segments | Yes | `python cli-tools/nf-profile` |
| `nf-trades` | Today's trades, historical P&L | Yes | `python cli-tools/nf-trades` |
| `nf-brokerage` | Pre-trade charges estimate | Yes | `python cli-tools/nf-brokerage RELIANCE 10` |
| `nf-options` | Option chain, greeks, buy/sell | Yes | `python cli-tools/nf-options chain NIFTY` |
| `nf-order` | Place, list, cancel orders | Yes | `python cli-tools/nf-order buy RELIANCE 10` |
| `nf-watchlist` | Manage watchlist with price alerts | Yes | `python cli-tools/nf-watchlist` |
| `nf-strategy` | Deploy strategy templates (algo trading) | Yes | `python cli-tools/nf-strategy deploy breakout --symbol RELIANCE --capital 50000 --entry 2450 --sl 2430 --json` |

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

---

### nf-funds

View available funds, margin, and buying power across equity and commodity segments.

```
python cli-tools/nf-funds [--json]
```

**Examples:**
```bash
python cli-tools/nf-funds              # Funds summary
python cli-tools/nf-funds --json       # JSON output
```

- Shows available margin, used margin, SPAN, exposure margin per segment
- Funds API may be unavailable 12 AM - 5:30 AM IST

---

### nf-profile

View Upstox account profile, active segments, and exchanges.

```
python cli-tools/nf-profile [--json]
```

**Examples:**
```bash
python cli-tools/nf-profile              # Profile summary
python cli-tools/nf-profile --json       # JSON output
```

- Shows user ID, name, email, broker, active segments (EQ, FO, etc.)

---

### nf-trades

View today's executed trades and historical trade P&L with charges.

```
python cli-tools/nf-trades [--json]
python cli-tools/nf-trades history [--segment EQ|FO] [--days N] [--json]
python cli-tools/nf-trades charges [--segment EQ|FO] [--json]
```

**Examples:**
```bash
python cli-tools/nf-trades                              # Today's trades
python cli-tools/nf-trades --json                       # JSON output
python cli-tools/nf-trades history                      # Last 30 days EQ
python cli-tools/nf-trades history --segment FO --days 90  # F&O 90 days
python cli-tools/nf-trades charges                      # P&L with charges
python cli-tools/nf-trades charges --segment FO         # F&O charges
```

- Today's trades show individual executions (an order may have multiple trades)
- Charges breakdown: brokerage, STT, GST, stamp duty, SEBI turnover, etc.

---

### nf-brokerage

Pre-trade brokerage and charges estimate before placing an order.

```
python cli-tools/nf-brokerage SYMBOL QTY [--side BUY|SELL] [--product D|I] [--price P] [--json]
```

**Examples:**
```bash
python cli-tools/nf-brokerage RELIANCE 10                    # Buy delivery estimate
python cli-tools/nf-brokerage RELIANCE 10 --side SELL        # Sell estimate
python cli-tools/nf-brokerage INFY 50 --product I            # Intraday estimate
python cli-tools/nf-brokerage TCS 5 --price 3500             # At specific price
python cli-tools/nf-brokerage RELIANCE 10 --json             # JSON output
```

- If no `--price`, uses current market price automatically
- Shows total charges as % of trade value

---

### nf-options

Options trading tool for Nifty/Bank Nifty and stock F&O.

```
python cli-tools/nf-options chain SYMBOL [--expiry EXP] [--json]
python cli-tools/nf-options live-chain SYMBOL YYYY-MM-DD [--json]
python cli-tools/nf-options greeks SYMBOL [--expiry EXP] [--strikes S1 S2] [--type CE|PE] [--json]
python cli-tools/nf-options expiries SYMBOL [--json]
python cli-tools/nf-options quote SYMBOL EXPIRY STRIKE CE|PE [--json]
python cli-tools/nf-options buy|sell SYMBOL EXPIRY STRIKE CE|PE LOTS [--price P] [--type MARKET|LIMIT] [--dry-run] [--json]
```

**Examples:**
```bash
python cli-tools/nf-options chain NIFTY                          # Option chain (cache)
python cli-tools/nf-options live-chain NIFTY 2026-03-13          # Live chain w/ greeks
python cli-tools/nf-options greeks NIFTY --expiry 17FEB          # All greeks for expiry
python cli-tools/nf-options greeks NIFTY --strikes 25000 25500 --type CE  # Filtered
python cli-tools/nf-options expiries BANKNIFTY                   # Upcoming expiries
python cli-tools/nf-options buy NIFTY 17FEB26 25500 PE 1         # Buy 1 lot
python cli-tools/nf-options sell NIFTY 17FEB26 25500 CE 2 --dry-run  # Preview sell
```

- `chain`: Uses cached instruments (fast, but prices may be stale)
- `live-chain`: Calls Upstox Put/Call API — real-time prices + greeks
- `greeks`: Uses Upstox v3 API for delta, gamma, theta, vega, IV (max 50 strikes)
- `buy`/`sell` are HITL-protected when called from the orchestrator

---

### nf-strategy

Deploy pre-built trading strategy templates as linked monitor rule sets. Each template creates multiple rules (entry, SL, target, trailing stop, auto square-off) from a single command.

```
python cli-tools/nf-strategy list [--json]
python cli-tools/nf-strategy deploy TEMPLATE --symbol SYM --capital AMOUNT [options] [--dry-run] [--json]
python cli-tools/nf-strategy status [--json]
python cli-tools/nf-strategy teardown --group-id UUID [--json]
```

**Available templates:** `orb`, `breakout`, `mean-reversion`, `vwap-bounce`, `scalp`

**Examples:**
```bash
python cli-tools/nf-strategy list --json                                          # List templates
python cli-tools/nf-strategy deploy orb --symbol RELIANCE --capital 50000 \
  --range-high 2460 --range-low 2440 --dry-run --json                             # Preview ORB
python cli-tools/nf-strategy deploy breakout --symbol HDFCBANK --capital 100000 \
  --entry 1650 --sl 1630 --json                                                   # Deploy breakout
python cli-tools/nf-strategy deploy mean-reversion --symbol INFY --capital 50000 \
  --sl 1850 --side long --json                                                    # Deploy mean reversion
python cli-tools/nf-strategy deploy scalp --symbol RELIANCE --capital 30000 \
  --entry 2450 --sl 2445 --max-entries 5 --json                                   # Deploy scalp
python cli-tools/nf-strategy status --json                                        # Show deployed strategies
python cli-tools/nf-strategy teardown --group-id <uuid> --json                    # Remove strategy
```

- All rules in a strategy share a `group_id` for easy management
- Use `--dry-run` to preview rules before creating them
- Default expiry is "today" (market close at 15:30 IST)
