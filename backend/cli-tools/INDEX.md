# Nifty Strategist CLI Tools

CLI tools for stock market data and trading operations. Run from `backend/` directory.

## Quick Reference

| Tool | Description | Needs Token | Example |
|------|-------------|-------------|---------|
| `nf-market-status` | Check if NSE market is open/closed | No | `python cli-tools/nf-market-status` |
| `nf-quote` | Get live quotes and historical data | Yes | `python cli-tools/nf-quote RELIANCE` |

## Tool Details

### nf-market-status

Check NSE market status — whether market is open, closed, or in pre-open session.

**Usage:**
```
python cli-tools/nf-market-status [--json]
```

**Flags:**
- `--json` — Output as JSON instead of human-readable text

**Examples:**
```bash
python cli-tools/nf-market-status          # Human-readable status
python cli-tools/nf-market-status --json   # JSON output
```

**Notes:**
- No API token needed (pure time-based calculation)
- Accounts for weekends and NSE holidays (2026 calendar)
- Shows time until next market open/close event
- IST timezone (UTC+5:30)

---

### nf-quote

Get live stock quotes or historical OHLCV candlestick data.

**Usage:**
```
python cli-tools/nf-quote SYMBOL [SYMBOL2 ...] [--json] [--historical --interval INTERVAL --days N]
python cli-tools/nf-quote --list
```

**Flags:**
- `--json` — Output as JSON
- `--list` — Show all 50 supported Nifty stock symbols
- `--historical` — Fetch OHLCV candle data instead of live quote
- `--interval` — Candle interval: `1minute`, `5minute`, `15minute`, `30minute`, `day` (default: `day`)
- `--days N` — Number of days of history (default: 30)

**Examples:**
```bash
python cli-tools/nf-quote RELIANCE                          # Live quote
python cli-tools/nf-quote RELIANCE TCS INFY                 # Multiple quotes
python cli-tools/nf-quote RELIANCE --json                   # JSON output
python cli-tools/nf-quote HDFCBANK --historical             # Daily OHLCV, 30 days
python cli-tools/nf-quote TCS --historical --interval 15minute --days 5  # Intraday candles
python cli-tools/nf-quote --list                            # All supported symbols
```

**Notes:**
- Requires `NF_ACCESS_TOKEN` env var (injected automatically by orchestrator)
- Supports all 50 Nifty stocks — use `--list` to see them
- Historical mode supports one symbol at a time
- Human-readable output shows last 20 candles; use `--json` for complete data
