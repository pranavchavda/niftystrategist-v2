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
| `nf-backtest` | Backtest strategies against historical data | Yes | `python cli-tools/nf-backtest --strategy breakout --symbol RELIANCE --days 30 --entry-pct 1.0 --sl-pct 1.5 --json` |
| `nf-backtest-scalp` | Backtest one scalp config (single symbol+indicator) | Yes | `python cli-tools/nf-backtest-scalp --symbol RELIANCE --days 30 --primary utbot --quantity 10 --json` |
| `nf-backtest-scan` | Signal-to-stock matching: rank all 10 indicators per candidate | Yes | `python cli-tools/nf-backtest-scan --universe nifty50 --top 10 --days 15 --json` |
| `nf-deploy-sessions` | Turn a signal-match scan into scalp sessions (dry-run default) | Yes | `python cli-tools/nf-deploy-sessions --universe nifty50 --top 15 --days 15` |
| `nf-mandate` | View/set/clear trading mandate for awakenings | No | `python cli-tools/nf-mandate show --json` |
| `nf-regime` | Classify the day as trending / range-bound / mixed | Yes | `python cli-tools/nf-regime --json` |

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
- `buy` and `cancel` require a render_ui confirmation card from the orchestrator (SAFETY-1) before execution

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
- `buy`/`sell` require a render_ui confirmation card from the orchestrator (SAFETY-1) before execution

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

---

### nf-backtest

Backtest strategy templates against historical data to validate performance before risking capital.

```
python cli-tools/nf-backtest --strategy TEMPLATE --symbol SYM [--days N] [--capital AMOUNT] [options] [--json]
python cli-tools/nf-backtest --strategy TEMPLATE --symbols SYM1,SYM2 [options] [--json]
```

**Examples:**
```bash
python cli-tools/nf-backtest --strategy breakout --symbol RELIANCE --days 30 \
  --entry-pct 1.0 --sl-pct 1.5 --json                                        # Breakout with % levels
python cli-tools/nf-backtest --strategy orb --symbol HDFCBANK --days 20 --json # ORB (auto-detects range)
python cli-tools/nf-backtest --strategy mean-reversion --symbol INFY \
  --days 30 --sl-pct 2.0 --json                                               # Mean reversion
python cli-tools/nf-backtest --strategy breakout --symbols RELIANCE,HDFCBANK,INFY \
  --days 30 --entry-pct 1.0 --sl-pct 1.5 --json                              # Compare across symbols
```

- Simulates candle-by-candle using the same rule evaluator as the live monitor
- Outputs: win rate, profit factor, Sharpe ratio, max drawdown, expectancy, trade list
- ORB auto-detects opening range from first candle of each day
- Use `--entry-pct` and `--sl-pct` for multi-day backtests (levels computed per day)

---

### nf-backtest-scan

Signal-to-stock matching engine. For each candidate stock, backtests **all 10 scalp
indicators** over a recent window and ranks which indicator historically works on
that stock — then emits a deployment plan. Runs in-process with the same state
machine + warm-up as the live scalper, so results match `POST /api/backtest/scalp`.

```
python cli-tools/nf-backtest-scan [--universe U] [--top N] [--days N] [--json]
python cli-tools/nf-backtest-scan --symbols SYM1,SYM2 [options] [--json]   # skip morning scan
```

**Examples:**
```bash
python cli-tools/nf-backtest-scan --universe nifty50 --top 10 --days 15 --json
python cli-tools/nf-backtest-scan --symbols SIEMENS,PERSISTENT --days 15        # explicit symbols
python cli-tools/nf-backtest-scan --indicators halftrend,ssl_hybrid \
  --symbols RELIANCE --min-profit-factor 1.5 --json
```

- Sources candidates by running `nf-morning-scan` internally (or pass `--symbols`)
- Fetches each symbol's candles **once**, reuses across all indicators (concurrent)
- Ranks indicators per stock by profit factor (net of charges), then net P&L
- Classifies each stock: `untradeable` (0 profitable indicators) / `signal_sensitive`
  (≤3) / `mixed` / `signal_agnostic` (≥7) — drives position sizing at deploy time
- `recommended` gives the best indicator + direction + confidence (gated on a real
  trade-count sample, so a 2-trade fluke never reads as "high")
- Results cached 24h on disk (`.backtest-cache/`, gitignored); keyed on full config
- `--entry-side auto` (default) backtests long-only AND short-only per indicator and
  keeps the better, so `recommended.direction` and the stats beside it always match the
  config that would actually be deployed
- `--min-trades N` (default 5): the adequate-sample floor — a 2-trade PF-inf fluke never
  outranks a robust signal, and "high" confidence requires both PF ≥ 3 and ≥ N trades
- Indicators: utbot, halftrend, ssl_hybrid, supertrend, ema_crossover, macd, qqe_mod,
  hilega_milega, volume_spike, renko (each run at its own engine-default params)

**Caveats:**
- `estimated_daily_pnl` is **in-sample / best-indicator-in-hindsight** — the winning
  indicator per stock is chosen on the same window its P&L is summed over. It overstates
  forward performance; treat it as an upper bound, never a forecast.
- `renko` (default `brick_size=10.0` fixed points) and `volume_spike` are judged at the
  live scalper's default params, which aren't price-aware — their ranking can be a sizing
  artifact on high- vs low-priced stocks. Tune their params before trusting them head-to-head.

Pairs with `nf-morning-scan --with-signal-match`, which folds this plan back into
the scan's scoring (untradeable → eliminated, agnostic → bonus) and adds
`best_signal` + `classification` to each candidate.

---

### nf-deploy-sessions

Turns a signal-match scan into live `nf-scalp` sessions — deploying the matched
indicator AND direction per stock. **Dry-run by default**: it only previews the
plan; `--execute` is required to actually create sessions.

```
python cli-tools/nf-deploy-sessions [scan-args] [--max-sessions N] [--execute] [--json]
python cli-tools/nf-deploy-sessions --plan-file SAVED_SCAN.json [options]
```

**Examples:**
```bash
python cli-tools/nf-deploy-sessions --universe nifty50 --top 15 --days 15        # preview only
python cli-tools/nf-deploy-sessions --universe nifty50 --top 15 --execute        # create sessions
python cli-tools/nf-deploy-sessions --plan-file /tmp/plan.json \
  --min-confidence high --risk-per-trade 6000 --execute                          # risk-sized, hi-conf only
```

- Sources the plan by running `nf-backtest-scan` (or reads `--plan-file`)
- Keeps tradeable stocks at/above `--min-confidence` (default medium), best first
- **Caps:** `--max-sessions` (default 12) and `--max-family-fraction` (default 0.4 →
  max ~40% of sessions on one indicator family: atr_trend / moving_avg / oscillator /
  volume). **No per-sector cap** — there is no symbol→sector map in the codebase yet
- **Sizing:** `--quantity` (fixed) > `--risk-per-trade` (qty = risk / (LTP × trail%)) >
  `--capital-per-trade` (default, qty = capital / LTP). `--use-mandate` pulls
  risk-per-trade from the trading mandate (best-effort parse of its free-text amount).
  Uses a **live LTP** for sizing, not the stale backtest close
- `--execute` creates each session via `nf-scalp create --mode equity_intraday`; without
  it, nothing is created
- Backtest stats shown are in-sample (see nf-backtest-scan caveats) — preview, sanity-check,
  then execute

---

### nf-mandate

View and manage the trading mandate for autonomous awakenings.

```
python cli-tools/nf-mandate show [--json]
python cli-tools/nf-mandate set [--risk-per-trade "₹5,000"] [--daily-loss-cap "₹10,000"] [--allowed-instruments "..."] [--cutoff-time "3:00 PM IST"] [--auto-squareoff-time "3:15 PM IST"] [--json]
python cli-tools/nf-mandate edit [--patch '<JSON>'] [--unset KEY] [--replace '<JSON>'] [--json]
python cli-tools/nf-mandate clear [--json]
```

**Examples:**
```bash
python cli-tools/nf-mandate show                                    # Current mandate
python cli-tools/nf-mandate show --json                             # JSON output
python cli-tools/nf-mandate set --risk-per-trade "₹5,000" \
  --daily-loss-cap "₹10,000" --allowed-instruments "Nifty 500"     # Set common fields
python cli-tools/nf-mandate edit --patch '{"pivot_authority": {"enabled": true, "max_pivots": 2}}'  # Edit nested fields
python cli-tools/nf-mandate edit --unset pivot_authority.max_pivots  # Remove a nested key
python cli-tools/nf-mandate clear                                   # Remove mandate
```

- Mandate defines risk boundaries for autonomous awakenings
- `set` covers the 6 common fields; `edit` reaches **any** field (incl. nested
  v2 structures) — `--patch` deep-merges JSON, `--unset` removes (dotted paths
  ok), `--replace` overwrites the whole mandate
- Merges with existing mandate (update, don't replace)
- Requires `NF_USER_ID` env var

---

### nf-regime

Market Regime Detector — classifies the current trading day as **trending**,
**range-bound**, or **mixed**, and recommends which strategy families fit.
Needs at least 3 five-minute candles to produce a result; the trend-quality
regression uses the first hour of trade, so the classification is most
reliable from ~10:15 IST onward. Designed to gate the morning awakening's
strategy choice.

```
python cli-tools/nf-regime [--json] [--tier1-count N] [--sector-leaders N] [--verbose]
```

**Examples:**
```bash
python cli-tools/nf-regime                          # Human-readable report
python cli-tools/nf-regime --json                   # Machine-readable
python cli-tools/nf-regime --tier1-count 3 --json    # Feed in morning-scan tier-1 count
python cli-tools/nf-regime --sector-leaders 2 --json # Feed in count of leading sectors
```

**How it works:** scores up to 9 signals, averages them into a composite, and
maps the composite to a regime:

| Signal | Source |
|--------|--------|
| Day range % | Nifty 5-min candles (today) |
| Trend quality (slope + R²) | Linear regression on first-hour closes |
| Oscillation (midpoint crossings) | Nifty 5-min candles |
| VIX level | Live `INDIAVIX` quote |
| Tier-1 candidate count | `--tier1-count` (from `nf-morning-scan`) |
| Net move % | Nifty open → current |
| Sector breadth | `--sector-leaders` (optional) |
| PCR (Put-Call Ratio) | NIFTY options — `nf-options pcr` (best-effort) |
| Change-in-OI flow | NIFTY options — `nf-options change-oi` (best-effort) |

- Composite `> 0.3` → **trending** (recommends orb, breakout, momentum)
- Composite `< -0.15` → **range-bound** (recommends mean-reversion, iron-condor, vwap-bounce, scalp)
- Otherwise → **mixed** (conservative: tier-1 ORB + theta)

**Notes:**
- `--tier1-count` / `--sector-leaders` are manual inputs — the tool does not
  run `nf-morning-scan` itself; the caller passes the counts.
- PCR and change-in-OI are fetched best-effort from NIFTY options (nearest
  expiry); if that data is unavailable the regime is computed from the rest.
- Live data only — there is no historical/backtest (`--date`) mode.
- VIX falls back to a neutral `20.0` if the live quote is unavailable.
- Always exits `0` on a successful classification (the regime is in stdout);
  non-zero is reserved for genuine failures.
- Requires `NF_ACCESS_TOKEN` (or `UPSTOX_ACCESS_TOKEN`); shells out to `nf-quote`.
